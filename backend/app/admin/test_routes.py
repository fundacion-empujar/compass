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
from app.users.get_user_preferences_repository import get_user_preferences_repository
from app.users.repositories import IUserPreferenceRepository
from app.users.sensitive_personal_data.types import SensitivePersonalDataRequirement
from app.users.types import UserPreferences

GIVEN_ADMIN_TOKEN = "admin-secret"  # nosec B105 - test fixture value
GIVEN_SEC_TOKEN = "sec-secret"  # nosec B105 - test fixture value
GIVEN_FRONTEND_URL = "https://app.example.test"

_VALID_SHARED_CODE_BODY = {"invitation_code": "grupo-2026", "invitation_type": "REGISTER"}


@pytest.fixture(autouse=True)
def _admin_env():
    prev = {k: os.environ.get(k) for k in ("ADMIN_TOKEN", "SEC_TOKEN", "FRONTEND_URL")}
    os.environ["ADMIN_TOKEN"] = GIVEN_ADMIN_TOKEN
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


@pytest.fixture
def mock_preferences_repo():
    repo = MagicMock(spec=IUserPreferenceRepository)

    async def _empty_stream(page_size, started_before, started_after):
        if False:  # default: an async generator that yields nothing
            yield []

    repo.stream_user_preferences = _empty_stream
    return repo


@pytest.fixture
def client(mock_invitation_repo, mock_preferences_repo):
    app = FastAPI()
    add_admin_routes(app)
    app.dependency_overrides[_get_user_invitation_repository] = lambda: mock_invitation_repo
    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_preferences_repo
    yield TestClient(app)
    app.dependency_overrides = {}


class TestAdminTokenGating:
    def test_missing_token_returns_401(self, client):
        response = client.get("/admin/registrations/export")
        assert response.status_code == HTTPStatus.UNAUTHORIZED

    def test_wrong_token_returns_403(self, client):
        response = client.get("/admin/registrations/export?token=not-the-token")
        assert response.status_code == HTTPStatus.FORBIDDEN

    def test_admin_token_not_configured_returns_503(self, client):
        os.environ.pop("ADMIN_TOKEN", None)
        response = client.get("/admin/registrations/export?token=whatever")
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE

    def test_trailing_exclamation_is_tolerated(self, client):
        # normalize_security_token strips a single trailing '!' (chat-app link mangling).
        response = client.get(f"/admin/registrations/export?token={GIVEN_ADMIN_TOKEN}!")
        assert response.status_code == HTTPStatus.OK


class TestRegistrationLinks:
    def test_creates_link(self, client):
        response = client.post(
            f"/admin/registration-links?token={GIVEN_ADMIN_TOKEN}",
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
            f"/admin/registration-links?token={GIVEN_ADMIN_TOKEN}",
            json={"registration_code": "0035cABC"},
        )
        assert response.status_code == HTTPStatus.OK
        assert response.json()["already_used"] is True

    def test_blank_registration_code_is_rejected(self, client):
        response = client.post(
            f"/admin/registration-links?token={GIVEN_ADMIN_TOKEN}",
            json={"registration_code": "   "},
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_missing_frontend_url_returns_503(self, client):
        os.environ.pop("FRONTEND_URL", None)
        response = client.post(
            f"/admin/registration-links?token={GIVEN_ADMIN_TOKEN}",
            json={"registration_code": "0035cABC"},
        )
        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE


class TestSharedCodes:
    def test_creates_shared_code_with_defaults(self, client, mock_invitation_repo):
        response = client.post(
            f"/admin/shared-codes?token={GIVEN_ADMIN_TOKEN}",
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
            f"/admin/shared-codes?token={GIVEN_ADMIN_TOKEN}",
            json={
                "invitation_code": "grupo-2026",
                "invitation_type": "LOGIN",
                "valid_from": "2026-12-31T00:00:00Z",
                "valid_until": "2026-01-01T00:00:00Z",
            },
        )
        assert response.status_code == HTTPStatus.BAD_REQUEST


class TestRegistrationsExport:
    def test_streams_csv_with_type_and_filters_codeless_rows(self, client, mock_preferences_repo):
        async def _stream(page_size, started_before, started_after):
            yield [
                # per-student tracking link: registration_code set ⇒ Tipo Individual
                UserPreferences(
                    user_id="user-1",
                    registration_code="0035cABC",
                    invitation_code="0035cABC",
                    accepted_tc=datetime(2026, 3, 1, tzinfo=timezone.utc),
                    sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
                ),
                # no codes at all ⇒ omitted
                UserPreferences(
                    user_id="user-2",
                    registration_code=None,
                    invitation_code=None,
                    sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
                ),
                # shared group code: no registration_code ⇒ Tipo Grupo
                UserPreferences(
                    user_id="user-3",
                    registration_code=None,
                    invitation_code="grupo-2026",
                    accepted_tc=datetime(2026, 4, 1, tzinfo=timezone.utc),
                    sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
                ),
                # formula-leading code ⇒ must be neutralized against CSV/Excel injection
                UserPreferences(
                    user_id="user-4",
                    registration_code=None,
                    invitation_code="=danger",
                    accepted_tc=datetime(2026, 5, 1, tzinfo=timezone.utc),
                    sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
                ),
            ]

        mock_preferences_repo.stream_user_preferences = _stream

        response = client.get(f"/admin/registrations/export?token={GIVEN_ADMIN_TOKEN}")
        assert response.status_code == HTTPStatus.OK
        assert "text/csv" in response.headers["content-type"]
        # UTF-8 BOM so Excel renders the Spanish headers correctly.
        assert response.content.startswith(b"\xef\xbb\xbf")

        lines = response.text.strip().splitlines()
        assert lines[0].lstrip("﻿") == "ID de usuario,Código usado,Tipo,Fecha de registro"
        # one "Código usado" column + a derived Tipo, instead of the confusing code pair
        assert any(line.startswith("user-1,0035cABC,Individual,") for line in lines)
        assert any(line.startswith("user-3,grupo-2026,Grupo,") for line in lines)
        # the row with no codes is omitted
        assert not any(line.startswith("user-2,") for line in lines)
        # CSV formula injection neutralized: a "="-leading code is prefixed with a quote
        assert "'=danger" in response.text
        assert ",=danger" not in response.text
