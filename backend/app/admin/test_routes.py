import os
from datetime import datetime, timezone
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.admin.routes import add_admin_routes, _get_user_invitation_repository
from app.invitations.repository import UserInvitationRepository
from app.invitations.types import ClaimSource, InvitationType, SecureLinkCodeClaim
from app.users.auth import Authentication, SignInProvider, UserInfo
from common_libs.test_utilities.mock_auth import MockAuth
from common_libs.test_utilities.random_data import get_random_base64_string

GIVEN_SEC_TOKEN = "sec-secret"  # nosec B105 - test fixture value
GIVEN_FRONTEND_URL = "https://app.example.test"

_VALID_SHARED_CODE_BODY = {"invitation_code": "grupo-2026", "invitation_type": "REGISTER"}


def _admin_user(*, super_admin: bool) -> UserInfo:
    return UserInfo(
        user_id="admin-1",
        name="Staff Admin",
        email="admin@example.org",
        token=get_random_base64_string(10),
        sign_in_provider=SignInProvider.PASSWORD,
        super_admin=super_admin,
    )


@pytest.fixture(autouse=True)
def _admin_env():
    # SEC_TOKEN and FRONTEND_URL are needed to assemble per-student registration links.
    prev = {k: os.environ.get(k) for k in ("SEC_TOKEN", "FRONTEND_URL")}
    os.environ["SEC_TOKEN"] = GIVEN_SEC_TOKEN
    os.environ["FRONTEND_URL"] = GIVEN_FRONTEND_URL
    yield
    for key, value in prev.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


@pytest.fixture
def mock_invitation_repo():
    repo = MagicMock(spec=UserInvitationRepository)
    repo.get_claim_by_registration_code = AsyncMock(return_value=None)
    repo.upsert_many_invitations = AsyncMock(return_value=None)
    return repo


def _build_client(*, super_admin: bool, mock_invitation_repo) -> TestClient:
    app = FastAPI()
    add_admin_routes(app, MockAuth(user=_admin_user(super_admin=super_admin)))
    app.dependency_overrides[_get_user_invitation_repository] = lambda: mock_invitation_repo
    return TestClient(app)


@pytest.fixture
def client(mock_invitation_repo):
    test_client = _build_client(super_admin=True, mock_invitation_repo=mock_invitation_repo)
    yield test_client
    test_client.app.dependency_overrides = {}


class TestSuperAdminGating:
    def test_non_super_admin_is_forbidden(self, mock_invitation_repo):
        # GIVEN an authenticated user WITHOUT the super_admin claim
        client = _build_client(super_admin=False, mock_invitation_repo=mock_invitation_repo)
        # WHEN they call any admin route
        # THEN every route rejects them with 403
        assert (
            client.post("/admin/shared-codes", json=_VALID_SHARED_CODE_BODY).status_code == HTTPStatus.FORBIDDEN
        )
        assert (
            client.post("/admin/registration-links", json={"registration_code": "0035cABC"}).status_code
            == HTTPStatus.FORBIDDEN
        )

    def test_super_admin_is_allowed(self, client):
        # GIVEN a super_admin (the default client fixture)
        # WHEN they call an admin route
        # THEN it succeeds, with no ?token= anywhere
        assert (
            client.post("/admin/registration-links", json={"registration_code": "0035cABC"}).status_code
            == HTTPStatus.OK
        )

    def test_admin_routes_emit_firebase_security_in_openapi(self):
        # GIVEN the admin routes mounted with the real Authentication (HTTPBearer "firebase")
        app = FastAPI()
        add_admin_routes(app, Authentication())
        # WHEN the OpenAPI schema is generated
        schema = app.openapi()
        # THEN the admin operation carries the firebase security requirement, so the API Gateway
        #      enforces a logged-in Firebase user at the edge (guards the gateway cutover).
        registration_links_op = schema["paths"]["/admin/registration-links"]["post"]
        assert {"firebase": []} in registration_links_op.get("security", [])


class TestRegistrationLinks:
    def test_creates_link(self, client):
        response = client.post(
            "/admin/registration-links",
            json={"registration_code": "0035cABC"},
        )
        assert response.status_code == HTTPStatus.OK
        body = response.json()
        assert body["link"].startswith(f"{GIVEN_FRONTEND_URL}/#/register?")
        assert "reg_code=0035cABC" in body["link"]
        assert f"report_token={GIVEN_SEC_TOKEN}" in body["link"]
        assert body["already_used"] is False

    def test_flags_already_used_code(self, client, mock_invitation_repo):
        mock_invitation_repo.get_claim_by_registration_code = AsyncMock(
            return_value=SecureLinkCodeClaim(
                registration_code="0035cABC",
                claimed_user_id="user-1",
                claimed_at=datetime.now(timezone.utc),
                claim_source=ClaimSource.SECURE_LINK,
            )
        )
        response = client.post(
            "/admin/registration-links",
            json={"registration_code": "0035cABC"},
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json()["already_used"] is True

    def test_blank_registration_code_is_rejected(self, client):
        response = client.post(
            "/admin/registration-links",
            json={"registration_code": "   "},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_missing_frontend_url_returns_503(self, client):
        os.environ.pop("FRONTEND_URL", None)
        response = client.post(
            "/admin/registration-links",
            json={"registration_code": "0035cABC"},
        )
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


class TestSharedCodes:
    def test_creates_shared_code_with_defaults(self, client, mock_invitation_repo):
        response = client.post(
            "/admin/shared-codes",
            json=_VALID_SHARED_CODE_BODY,
        )
        assert response.status_code == HTTPStatus.CREATED
        body = response.json()
        assert body["invitation_code"] == "grupo-2026"
        assert body["allowed_usage"] == 999999

        mock_invitation_repo.upsert_many_invitations.assert_awaited_once()
        created = mock_invitation_repo.upsert_many_invitations.call_args[0][0]
        assert len(created) == 1
        assert created[0].invitation_code == "grupo-2026"
        assert created[0].invitation_type == InvitationType.REGISTER
        assert created[0].remaining_usage == 999999
        assert created[0].valid_until > created[0].valid_from

    def test_rejects_inverted_validity_window(self, client):
        response = client.post(
            "/admin/shared-codes",
            json={
                "invitation_code": "grupo-2026",
                "invitation_type": "LOGIN",
                "valid_from": "2026-12-31T00:00:00Z",
                "valid_until": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST
