def normalize_security_token(value: str | None) -> str | None:
    """
    Normalize a SEC_TOKEN-equivalent value for comparison.

    Casefolds the value and strips a single trailing '!' so that links whose
    trailing exclamation mark was dropped by chat-app auto-link parsers
    (WhatsApp, Telegram, etc.) still validate. Returns None for None or empty
    input so callers can keep their existing "Security token required" branch.
    """
    if value is None:
        return None
    normalized = value.casefold()
    if normalized.endswith("!"):
        normalized = normalized[:-1]
    return normalized or None
