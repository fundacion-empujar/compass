import os

import pytest
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.users.cv.routes import add_public_report_routes
from app.users.repositories import IUserPreferenceRepository
from app.users.types import UserPreferences, SensitivePersonalDataRequirement
from app.conversations.experience.service import IExperienceService
from app.conversations.experience.get_experience_service import get_experience_service
from app.users.get_user_preferences_repository import get_user_preferences_repository


@pytest.fixture
def app():
    app = FastAPI()
    add_public_report_routes(app)
    return app


@pytest.fixture(autouse=True)
def clear_security_tokens(monkeypatch):
    # Reports are gated by ADMIN_TOKEN (fail-closed); start each test from a clean slate.
    monkeypatch.delenv("SEC_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)

@pytest.mark.asyncio
@pytest.mark.parametrize("link_token", ["fundacion-empujar-2026!", "fundacion-empujar-2026"])
async def test_report_lookup_accepts_token_with_or_without_trailing_bang(app, monkeypatch, link_token):
    """Chat-app auto-link parsers strip a trailing '!'. With ADMIN_TOKEN ending in '!',
    both the original and the truncated token in the URL must validate."""
    monkeypatch.setenv("ADMIN_TOKEN", "fundacion-empujar-2026!")

    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref = UserPreferences(
        user_id="user-from-reg",
        sessions=[987],
        sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
    )
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=mock_pref)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=None)

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(f"/reports/reg-123?token={link_token}")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["user_id"] == "user-from-reg"


@pytest.mark.asyncio
async def test_report_lookup_rejects_unrelated_token_even_with_bang_tolerance(app, monkeypatch):
    """Regression guard: tolerance only strips a trailing '!', not arbitrary substrings."""
    monkeypatch.setenv("ADMIN_TOKEN", "fundacion-empujar-2026!")

    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=None)

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/reg-123?token=completely-different")

    assert response.status_code == HTTPStatus.FORBIDDEN
    mock_pref_repo.get_user_preference_by_registration_code.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_lookup_accepts_case_insensitive_token(app, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "SeCrEt")

    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref = UserPreferences(
        user_id="user-from-reg",
        sessions=[987],
        sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
    )
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=mock_pref)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=None)

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/reg-123?token=secret")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["user_id"] == "user-from-reg"
    mock_pref_repo.get_user_preference_by_registration_code.assert_awaited_once_with("reg-123")
    mock_pref_repo.get_user_preference_by_user_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_lookup_prefers_registration_code(app, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")

    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref = UserPreferences(
        user_id="user-from-reg",
        sessions=[987],
        sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
    )
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=mock_pref)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=None)

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/reg-123?token=admin-secret")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["user_id"] == "user-from-reg"
    mock_pref_repo.get_user_preference_by_registration_code.assert_awaited_once_with("reg-123")
    mock_pref_repo.get_user_preference_by_user_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_report_lookup_falls_back_to_user_id(app, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")

    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(
        return_value=UserPreferences(
            user_id="user-123",
            sessions=[42],
            sensitive_personal_data_requirement=SensitivePersonalDataRequirement.NOT_AVAILABLE,
        )
    )

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/user-123?token=admin-secret")

    assert response.status_code == HTTPStatus.OK
    assert response.json()["user_id"] == "user-123"
    mock_pref_repo.get_user_preference_by_registration_code.assert_awaited_once_with("user-123")
    mock_pref_repo.get_user_preference_by_user_id.assert_awaited_once_with("user-123")


@pytest.mark.asyncio
async def test_report_lookup_not_found(app, monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "admin-secret")

    mock_pref_repo = MagicMock(spec=IUserPreferenceRepository)
    mock_pref_repo.get_user_preference_by_registration_code = AsyncMock(return_value=None)
    mock_pref_repo.get_user_preference_by_user_id = AsyncMock(return_value=None)

    mock_exp_service = MagicMock(spec=IExperienceService)
    mock_exp_service.get_experiences_by_session_id = AsyncMock(return_value=[])

    app.dependency_overrides[get_user_preferences_repository] = lambda: mock_pref_repo
    app.dependency_overrides[get_experience_service] = lambda: mock_exp_service

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/reports/unknown?token=admin-secret")

    assert response.status_code == HTTPStatus.NOT_FOUND
    mock_pref_repo.get_user_preference_by_registration_code.assert_awaited_once_with("unknown")
    mock_pref_repo.get_user_preference_by_user_id.assert_awaited_once_with("unknown")
