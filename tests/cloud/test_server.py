from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path

from canon.server.polar import plan_from_webhook, verify_signature
from canon.server.store import CloudStore


def test_store_login_snapshot_and_invite(tmp_path: Path) -> None:
    db = CloudStore(tmp_path / "cloud.db")
    started = db.create_device()
    user = db.approve_device(
        started["user_code"], email="dev@example.com", name="Dev"
    )
    finished = db.finish_device(started["device_code"])
    assert finished is not None
    assert finished["status"] == "approved"
    assert finished["token"]
    loaded = db.user_from_token(str(finished["token"]))
    assert loaded is not None
    assert loaded["email"] == "dev@example.com"

    db.ensure_workspace("acme/demo", user)
    count = db.save_snapshot(
        "acme/demo",
        {"format": "canon-export", "decisions": [{"title": "Use PostgreSQL"}]},
        str(user["id"]),
    )
    assert count == 1
    pulled = db.load_snapshot("acme/demo")
    assert pulled is not None
    assert pulled["snapshot"]["decisions"][0]["title"] == "Use PostgreSQL"
    code = db.create_invite("acme/demo", "teammate@example.com")
    other = db.upsert_user(email="teammate@example.com", name="Other")
    db.accept_invite(code, other)
    emails = [row["email"] for row in db.members("acme/demo")]
    assert "dev@example.com" in emails
    assert "teammate@example.com" in emails
    db.close()


def test_polar_signature_and_plan() -> None:
    secret = "whsec_test"
    payload = {
        "type": "subscription.active",
        "data": {
            "status": "active",
            "customer_id": "cus_1",
            "metadata": {"user_id": "u1", "plan": "pro"},
        },
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw, hashlib.sha256).hexdigest()
    import os

    os.environ["POLAR_WEBHOOK_SECRET"] = secret
    assert verify_signature(raw, sig)
    user_id, plan, customer = plan_from_webhook(payload)
    assert user_id == "u1"
    assert plan == "pro"
    assert customer == "cus_1"
