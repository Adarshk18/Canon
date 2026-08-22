from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import unquote

from canon.server.polar import (
    PolarError,
    create_checkout,
    plan_from_webhook,
    verify_signature,
)
from canon.server.polar import configured as polar_configured
from canon.server.store import SEATS, CloudStore, default_db_path

try:
    from fastapi import FastAPI, Header, HTTPException, Request
    from fastapi.responses import HTMLResponse, JSONResponse
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "Install the server extra:\n\n    pip install 'canon-memory[server]'\n"
    ) from exc


def open_sync() -> bool:
    return os.environ.get("CANON_CLOUD_OPEN_SYNC", "").lower() in {"1", "true", "yes"}


def create_app(store: CloudStore | None = None) -> FastAPI:
    db = store or CloudStore(default_db_path())
    app = FastAPI(title="Canon Cloud", version="1.3.0")

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return (
            "<!doctype html><html><head><meta charset='utf-8'><title>Canon Cloud</title>"
            "<style>body{font-family:sans-serif;max-width:40rem;margin:3rem auto;color:#111}"
            "a{color:#0b57d0}</style></head><body>"
            "<h1>Canon Cloud</h1>"
            "<p>Optional sync and seats. Local Canon does not need this.</p>"
            "<p><a href='/health'>Health</a> · <a href='/device'>Sign in a CLI</a></p>"
            "</body></html>"
        )

    def current_user(authorization: str | None) -> dict[str, Any]:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(401, "Sign in with `canon cloud login`.")
        user = db.user_from_token(authorization.split(" ", 1)[1].strip())
        if user is None:
            raise HTTPException(401, "Session expired. Run `canon cloud login`.")
        return user

    def require_member(slug: str, user: dict[str, Any]) -> dict[str, Any]:
        slug = unquote(slug).lower()
        existing = db.membership(slug, str(user["id"]))
        if existing:
            return existing
        # First pusher owns the workspace.
        db.ensure_workspace(slug, user)
        member = db.membership(slug, str(user["id"]))
        if member is None:
            raise HTTPException(403, "Not a member of this workspace.")
        return member

    def can_sync(user: dict[str, Any]) -> bool:
        if open_sync():
            return True
        return str(user.get("plan") or "free") in {"pro", "team"}

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "polar": polar_configured(), "open_sync": open_sync()}

    @app.post("/v1/device/start")
    def device_start() -> dict[str, Any]:
        started = db.create_device()
        base = os.environ.get("CANON_CLOUD_PUBLIC_URL", "http://127.0.0.1:8787").rstrip("/")
        return {
            **started,
            "interval": 2,
            "verify_url": f"{base}/device?code={started['user_code']}",
        }

    @app.post("/v1/device/poll")
    def device_poll(body: dict[str, Any]) -> dict[str, Any]:
        code = str(body.get("device_code") or "")
        result = db.finish_device(code)
        if result is None:
            raise HTTPException(400, "Unknown device code.")
        return result

    @app.get("/device", response_class=HTMLResponse)
    def device_page(code: str = "") -> str:
        return DEVICE_PAGE.replace("{{CODE}}", code)

    @app.post("/v1/device/approve")
    def device_approve(body: dict[str, Any]) -> dict[str, Any]:
        user_code = str(body.get("user_code") or body.get("code") or "")
        email = str(body.get("email") or "").strip()
        name = str(body.get("name") or email.split("@")[0] or "user")
        if "@" not in email:
            raise HTTPException(400, "A valid email is required.")
        try:
            user = db.approve_device(user_code, email=email, name=name)
        except KeyError:
            raise HTTPException(400, "That code is invalid or expired.") from None
        return {"ok": True, "email": user["email"], "plan": user["plan"]}

    @app.get("/v1/me")
    def me(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        user = current_user(authorization)
        plan = str(user.get("plan") or "free")
        return {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "plan": plan,
            "seats": SEATS.get(plan, 0),
        }

    @app.post("/v1/billing/checkout")
    def billing_checkout(
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = current_user(authorization)
        plan = str(body.get("plan") or "pro").lower()
        if plan not in {"pro", "team"}:
            raise HTTPException(400, "Plan must be pro or team.")
        success = os.environ.get(
            "POLAR_SUCCESS_URL",
            os.environ.get("CANON_CLOUD_PUBLIC_URL", "http://127.0.0.1:8787") + "/paid",
        )
        try:
            url = create_checkout(
                plan=plan,
                email=str(user["email"]),
                user_id=str(user["id"]),
                success_url=success,
            )
        except PolarError as exc:
            raise HTTPException(503, str(exc)) from exc
        return {"url": url, "provider": "polar"}

    @app.get("/paid", response_class=HTMLResponse)
    def paid() -> str:
        return "<html><body><p>Payment received. Return to the terminal and run <code>canon cloud status</code>.</p></body></html>"

    @app.post("/v1/billing/polar")
    async def polar_webhook(
        request: Request,
        webhook_signature: str | None = Header(default=None, alias="webhook-signature"),
    ) -> JSONResponse:
        raw = await request.body()
        if not verify_signature(raw, webhook_signature):
            raise HTTPException(401, "Invalid Polar signature.")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid webhook.") from None
        if not isinstance(payload, dict):
            raise HTTPException(400, "Invalid webhook.")
        user_id, plan, customer = plan_from_webhook(payload)
        if user_id and plan:
            db.set_plan(user_id, plan, polar_customer=customer)
        return JSONResponse({"ok": True})

    @app.put("/v1/workspaces/{slug:path}/snapshot")
    def push_snapshot(
        slug: str,
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = current_user(authorization)
        if not can_sync(user):
            raise HTTPException(
                402,
                "Cloud sync requires a Pro or Team plan. Run `canon cloud upgrade pro`.",
            )
        slug = unquote(slug).lower()
        require_member(slug, user)
        snapshot = body.get("snapshot")
        if not isinstance(snapshot, dict) or snapshot.get("format") != "canon-export":
            raise HTTPException(400, "Payload must be a Canon export.")
        count = db.save_snapshot(slug, snapshot, str(user["id"]))
        return {"ok": True, "workspace": slug, "count": count}

    @app.get("/v1/workspaces/{slug:path}/snapshot")
    def pull_snapshot(
        slug: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = current_user(authorization)
        if not can_sync(user):
            raise HTTPException(402, "Cloud sync requires a Pro or Team plan.")
        slug = unquote(slug).lower()
        require_member(slug, user)
        loaded = db.load_snapshot(slug)
        if loaded is None:
            raise HTTPException(404, "No snapshot for this workspace yet. Run `canon cloud push`.")
        return loaded

    @app.post("/v1/workspaces/{slug:path}/invites")
    def invite(
        slug: str,
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = current_user(authorization)
        slug = unquote(slug).lower()
        member = require_member(slug, user)
        if member.get("role") != "owner":
            raise HTTPException(403, "Only the workspace owner can invite.")
        email = str(body.get("email") or "").strip().lower()
        if "@" not in email:
            raise HTTPException(400, "A valid email is required.")
        plan = str(user.get("plan") or "free")
        limit = SEATS.get(plan, 0)
        if not open_sync() and db.member_count(slug) >= max(limit, 1):
            raise HTTPException(402, f"{plan} plan allows {limit} seat(s).")
        code = db.create_invite(slug, email)
        return {"code": code, "email": email, "workspace": slug}

    @app.post("/v1/invites/accept")
    def accept(
        body: dict[str, Any],
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = current_user(authorization)
        code = str(body.get("code") or "").strip()
        try:
            result = db.accept_invite(code, user)
        except KeyError:
            raise HTTPException(404, "Invite not found.") from None
        return result

    @app.get("/v1/workspaces/{slug:path}/members")
    def members(
        slug: str,
        authorization: str | None = Header(default=None),
    ) -> dict[str, Any]:
        user = current_user(authorization)
        slug = unquote(slug).lower()
        require_member(slug, user)
        return {"workspace": slug, "members": db.members(slug)}

    return app


DEVICE_PAGE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <title>Canon Cloud login</title>
  <style>
    body { font-family: sans-serif; max-width: 28rem; margin: 4rem auto; }
    input, button { font: inherit; padding: 0.4rem; width: 100%; margin: 0.3rem 0; }
  </style>
</head>
<body>
  <h1>Canon Cloud</h1>
  <p>Confirm this device. Local Canon still works if you close this page.</p>
  <form id="f">
    <label>Code <input name="code" value="{{CODE}}" required/></label>
    <label>Email <input name="email" type="email" required/></label>
    <label>Name <input name="name"/></label>
    <button type="submit">Approve</button>
  </form>
  <p id="out"></p>
  <script>
    const form = document.getElementById("f");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(form));
      const res = await fetch("/v1/device/approve", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({user_code: data.code, email: data.email, name: data.name})
      });
      const body = await res.json();
      document.getElementById("out").textContent = res.ok
        ? "Approved. Return to the terminal."
        : (body.detail || "Could not approve.");
    });
  </script>
</body>
</html>
"""
