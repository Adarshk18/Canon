"""Polar.sh checkout + webhooks. Stripe is not used (India is invite-only)."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from typing import Any


class PolarError(RuntimeError):
    pass


def configured() -> bool:
    return bool(os.environ.get("POLAR_ACCESS_TOKEN") and _product("pro"))


def _product(plan: str) -> str:
    key = "POLAR_PRODUCT_PRO" if plan == "pro" else "POLAR_PRODUCT_TEAM"
    return os.environ.get(key, "").strip()


def create_checkout(*, plan: str, email: str, user_id: str, success_url: str) -> str:
    token = os.environ.get("POLAR_ACCESS_TOKEN", "").strip()
    product = _product(plan)
    if not token or not product:
        raise PolarError("Polar is not configured.")
    body = {
        "products": [product],
        "success_url": success_url,
        "customer_email": email,
        "metadata": {"user_id": user_id, "plan": plan},
    }
    req = urllib.request.Request(
        "https://api.polar.sh/v1/checkouts/",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise PolarError(detail or f"HTTP {exc.code}") from exc
    url = payload.get("url") if isinstance(payload, dict) else None
    if not isinstance(url, str) or not url:
        raise PolarError("Polar did not return a checkout URL.")
    return url


def verify_signature(raw: bytes, header: str | None) -> bool:
    secret = os.environ.get("POLAR_WEBHOOK_SECRET", "").strip()
    if not secret:
        return False
    if not header:
        return False
    digest = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    expected = header.removeprefix("sha256=")
    return hmac.compare_digest(digest, expected)


def plan_from_webhook(payload: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """Return (user_id, plan, polar_customer) if this event should change access."""
    event = str(payload.get("type") or "")
    data = payload.get("data")
    if not isinstance(data, dict):
        return None, None, None
    raw_meta = data.get("metadata")
    metadata: dict[str, Any] = raw_meta if isinstance(raw_meta, dict) else {}
    user_id = str(metadata.get("user_id") or "") or None
    plan = str(metadata.get("plan") or "") or None
    customer = data.get("customer_id") or data.get("id")
    customer_id = str(customer) if customer else None
    if event.endswith("revoked") or event.endswith("canceled") or "refund" in event:
        return user_id, "free", customer_id
    if "active" in event or event.endswith("updated") or "checkout" in event:
        if data.get("status") in {None, "open", "failed", "expired"}:
            if event.startswith("checkout") and data.get("status") != "succeeded":
                return None, None, None
        return user_id, plan or "pro", customer_id
    return None, None, None
