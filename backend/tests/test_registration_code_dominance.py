import pytest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.users.cv.routes import add_public_report_routes
from app.users.auth import SignInProvider, UserInfo
from app.users.repositories import IUserPreferenceRepository
from app.users.types import UserPreferences, SensitivePersonalDataRequirement
from app.conversations.experience.service import IExperienceService
from app.conversations.experience.get_experience_service import get_experience_service
from app.users.get_user_preferences_repository import get_user_preferences_repository
from common_libs.test_utilities.mock_auth import MockAuth
from common_libs.test_utilities.random_data import get_random_base64_string


def _admin_user() -> UserInfo:
    return UserInfo(
        user_id="admin-1",
        name="Staff Admin",
        email="admin@example.org",
        token=get_random_base64_string(10),
        sign_in_provider=SignInProvider.PASSWORD,
        super_admin=True,
    )


@pytest.fixture
def app():
    app = FastAPI()
    # Reports are gated on the Firebase super_admin claim; a granted staff user reaches the lookup logic.
    add_public_report_routes(app, MockAuth(user=_admin_user()))
    return app


@pytest.mark.asyncio
async def test_report_user_id_rejected_when_registration_code_present(app):
    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(
        return_value=UserPreferences(
            user_id="user-123",
            registration_code="reg-999",
            sessions=[42],
            sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
        )
    )

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/user-123")

    assert response.status_code == HTTPStatus.NOT_FOUND
    mock_pref_repo.get_user_preference_by_registration_code.assert_awaited_once_with("user-123")
    mock_pref_repo.get_user_preference_by_user_id.assert_awaited_once_with("user-123")


@pytest.mark.asyncio
async def test_report_user_id_allowed_when_registration_code_absent(app):
    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(
        return_value=UserPreferences(
            user_id="user-123",
            registration_code=None,
            sessions=[42],
            sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
        )
    )

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/user-123")

    assert response.status_code == HTTPStatus.OK
    mock_pref_repo.get_user_preference_by_registration_code.assert_awaited_once_with("user-123")
    mock_pref_repo.get_user_preference_by_user_id.assert_awaited_once_with("user-123")
