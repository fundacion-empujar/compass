from http import HTTPStatus

import pytest
from fastapi import HTTPException

from app.security_token import is_registration_code_disabled, normalize_security_token, validate_report_token


@pytest.mark.parametrize(
    "given,expected",
    [
        (None, None),
        ("", None),
        ("abc", "abc"),
        ("ABC", "abc"),
        ("AbC", "abc"),
        ("abc!", "abc"),
        ("ABC!", "abc"),
        ("abc!!", "abc!"),
        ("!", None),
        ("fundacion-empujar-2026!", "fundacion-empujar-2026"),
        ("fundacion-empujar-2026", "fundacion-empujar-2026"),
        ("Fundacion-Empujar-2026!", "fundacion-empujar-2026"),
    ],
)
def test_normalize_security_token(given, expected):
    assert normalize_security_token(given) == expected


def test_normalize_security_token_makes_with_and_without_trailing_bang_equal():
    """Whether or not WhatsApp dropped the trailing '!', both forms must compare equal."""
    deployed = normalize_security_token("fundacion-empujar-2026!")
    from_link_with_bang = normalize_security_token("fundacion-empujar-2026!")
    from_link_without_bang = normalize_security_token("fundacion-empujar-2026")
    assert deployed == from_link_with_bang
    assert deployed == from_link_without_bang


def test_normalize_security_token_does_not_match_unrelated_value():
    assert normalize_security_token("fundacion-empujar-2026!") != normalize_security_token("wrong-token")


@pytest.fixture(autouse=True)
def _clear_application_config():
    """validate_report_token falls back to the env var when no application config is set up."""
    from app.app_config import set_application_config
    set_application_config(None)
    yield
    set_application_config(None)


def test_validate_report_token_accepts_matching_token(monkeypatch):
    monkeypatch.delenv("GLOBAL_DISABLE_REGISTRATION_CODE", raising=False)
    monkeypatch.setenv("SEC_TOKEN", "token-abc")

    validate_report_token("token-abc")  # does not raise


def test_validate_report_token_requires_a_token(monkeypatch):
    monkeypatch.delenv("GLOBAL_DISABLE_REGISTRATION_CODE", raising=False)
    monkeypatch.setenv("SEC_TOKEN", "token-abc")

    with pytest.raises(HTTPException) as excinfo:
        validate_report_token(None)

    assert excinfo.value.status_code == HTTPStatus.UNAUTHORIZED
    assert "Security token required" in str(excinfo.value.detail)


def test_validate_report_token_rejects_a_wrong_token(monkeypatch):
    monkeypatch.delenv("GLOBAL_DISABLE_REGISTRATION_CODE", raising=False)
    monkeypatch.setenv("SEC_TOKEN", "token-abc")

    with pytest.raises(HTTPException) as excinfo:
        validate_report_token("something-else")

    assert excinfo.value.status_code == HTTPStatus.FORBIDDEN
    assert "Invalid security token" in str(excinfo.value.detail)


@pytest.mark.parametrize("given_report_token", [None, "", "something-else"])
def test_validate_report_token_is_skipped_when_registration_code_is_disabled(monkeypatch, given_report_token):
    """With GLOBAL_DISABLE_REGISTRATION_CODE on, the frontend sends no report token, so none may be required."""
    monkeypatch.setenv("GLOBAL_DISABLE_REGISTRATION_CODE", "True")
    monkeypatch.setenv("SEC_TOKEN", "token-abc")

    validate_report_token(given_report_token)  # does not raise


def test_validate_report_token_is_skipped_when_disabled_via_application_config(monkeypatch):
    """The application config is the source of truth when it has been set up."""
    from app.app_config import set_application_config
    from unittest.mock import MagicMock
    from app.app_config import ApplicationConfig

    monkeypatch.delenv("GLOBAL_DISABLE_REGISTRATION_CODE", raising=False)
    monkeypatch.setenv("SEC_TOKEN", "token-abc")
    set_application_config(MagicMock(spec=ApplicationConfig, disable_registration_code=True))

    assert is_registration_code_disabled() is True
    validate_report_token(None)  # does not raise
