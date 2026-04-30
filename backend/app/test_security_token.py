import pytest

from app.security_token import normalize_security_token


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
