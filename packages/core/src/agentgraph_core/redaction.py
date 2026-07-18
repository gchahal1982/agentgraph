"""Conservative redaction for audit and diagnostic payloads."""
from __future__ import annotations

import re
from typing import Any

from agentgraph_core.types import JSONValue

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {
    "authorization",
    "api_key",
    "apikey",
    "access_token",
    "refresh_token",
    "token",
    "password",
    "secret",
    "private_key",
    "client_secret",
    "cookie",
    "session_id",
}
_PRIVATE_KEY = re.compile(
    r"-----BEGIN(?: [A-Z0-9]+)? PRIVATE KEY-----.*?-----END(?: [A-Z0-9]+)? PRIVATE KEY-----",
    re.DOTALL,
)
_AUTHORIZATION = re.compile(
    r"(?i)\b(authorization\s*:\s*(?:basic|bearer)\s+)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\b(bearer\s+)(?:\"[^\"]*\"|'[^']*'|[A-Za-z0-9._~+/=-]+)")
_URL_USERINFO = re.compile(r"(?i)(\b[a-z][a-z0-9+.-]*://)[^/@\s]+@")
_KEY_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|token|password|secret|"
    r"private[_-]?key|client[_-]?secret|session[_-]?id)\s*([=:])\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_COOKIE = re.compile(r"(?i)\b(cookie\s*:\s*)[^\r\n]+")


def redact_sensitive(value: Any, *, key: str | None = None) -> JSONValue:
    """Return a JSON-compatible copy with common credential forms removed."""
    normalized_key = key.lower().replace("-", "_") if key is not None else None
    if normalized_key in _SENSITIVE_KEYS:
        return _REDACTED
    if isinstance(value, dict):
        return {str(k): redact_sensitive(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        value = _PRIVATE_KEY.sub(_REDACTED, value)
        value = _AUTHORIZATION.sub(lambda match: f"{match.group(1)}{_REDACTED}", value)
        value = _BEARER.sub(lambda match: f"{match.group(1)}{_REDACTED}", value)
        value = _URL_USERINFO.sub(lambda match: f"{match.group(1)}{_REDACTED}@", value)
        value = _COOKIE.sub(lambda match: f"{match.group(1)}{_REDACTED}", value)
        return _KEY_VALUE.sub(
            lambda match: f"{match.group(1)}{match.group(2)}{_REDACTED}", value
        )
    if value is None or isinstance(value, bool | int | float):
        return value
    return str(value)
