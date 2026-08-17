from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from canon.errors import CloudError
from canon.security.redact import redact


def request_json(
    method: str,
    url: str,
    *,
    token: str | None = None,
    payload: dict[str, Any] | None = None,
    timeout: float = 20.0,
) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/json", "User-Agent": "canon-memory"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        detail = _error_detail(body)
        raise CloudError(
            f"Canon Cloud returned HTTP {exc.code}.",
            redact(detail) if detail else "Check CANON_CLOUD_URL and `canon cloud login`.",
        ) from exc
    except urllib.error.URLError as exc:
        raise CloudError(
            "Could not reach Canon Cloud.",
            "Set CANON_CLOUD_URL to your server, or keep using Canon locally.",
        ) from exc
    if not raw.strip():
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise CloudError("Canon Cloud returned an unexpected payload.")
    return parsed


def _error_detail(body: str) -> str:
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return body[:240]
    if isinstance(parsed, dict):
        for key in ("detail", "message", "error"):
            value = parsed.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return body[:240]
