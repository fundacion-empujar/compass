import os
import pytest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock
from app.users.cv.routes import add_public_report_routes
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from app.users.repositories import IUserPreferenceRepository
from app.conversations.experience.service import IExperienceService
from app.conversations.experience.get_experience_service import get_experience_service
from app.users.get_user_preferences_repository import get_user_preferences_repository
from app.agent.experience import ExperienceEntity

@pytest.fixture
def app():
    app = FastAPI()
    add_public_report_routes(app)
    return app

@pytest.fixture(autouse=True)
def _admin_token_env():
    # Reports are gated by ADMIN_TOKEN (fail-closed); configure it for these business-logic tests.
    os.environ["ADMIN_TOKEN"] = "test-admin-token"
    yield
    os.environ.pop("ADMIN_TOKEN", None)

@pytest.mark.asyncio
async def test_get_public_report_success(app):
    # Mock repositories and services
    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_exp_service = MagicMock(spec=IExperienceService)
    
    mock_preferences = MagicMock()
    mock_preferences.user_id = "user-1"
    mock_preferences.registration_code = None
    mock_preferences.sessions = [123]
    mock_preferences.accepted_tc = None
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=mock_preferences)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    
    # Mock ExperienceEntity and phase
    mock_entity = MagicMock(spec=ExperienceEntity)
    mock_entity.uuid = "exp-1"
    mock_entity.experience_title = "Developer"
    mock_entity.normalized_experience_title = "Software Developer"
    mock_entity.company = "Tech Corp"
    mock_entity.timeline = None
    mock_entity.work_type = None
    mock_entity.top_skills = []
    mock_entity.remaining_skills = []
    mock_entity.summary = "A dev"
    
    mock_phase = MagicMock()
    mock_phase.name = "PROCESSED"
    
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[(mock_entity, mock_phase)])
    
    # Override dependencies
    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/user-1?token=test-admin-token")
    
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["user_id"] == "user-1"
    assert len(data["experiences"]) == 1
    # raw title is preserved AND the normalized title is carried through to the response
    assert data["experiences"][0]["experience_title"] == "Developer"
    assert data["experiences"][0]["normalized_experience_title"] == "Software Developer"

@pytest.mark.asyncio
async def test_get_public_report_not_found(app):
    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=None)

    mock_exp_service = MagicMock(spec=IExperienceService)

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/user-2?token=test-admin-token")
    
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert response.json()["detail"] == "No report data found for this user"
