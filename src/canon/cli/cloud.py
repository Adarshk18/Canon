from __future__ import annotations

import time
from typing import Any

import typer

from canon.cloud.client import CloudClient
from canon.cloud.credentials import (
    CloudCredentials,
    clear_credentials,
    default_base_url,
    load_credentials,
    save_credentials,
)
from canon.errors import CloudError, UsageError
from canon.integrations.snapshot import refresh_injection_files
from canon.output.console import Console
from canon.runtime import load_runtime


def _json_flag() -> Any:
    return typer.Option(False, "--json", help="Machine-readable JSON output.")


def _use_json(json_output: bool) -> Console:
    return Console(force_json=json_output)


def _runtime() -> Any:
    return load_runtime(require_init=True)

cloud_app = typer.Typer(
    name="cloud",
    help="Optional Canon Cloud sync and team sharing. Not required for local use.",
    no_args_is_help=True,
)


def _workspace_slug(runtime_repo: Any) -> str:
    slug = runtime_repo.github_slug()
    if isinstance(slug, str) and slug:
        return slug.lower()
    name = str(runtime_repo.root.name)
    return name.lower().replace(" ", "-")


@cloud_app.command("login")
def login_cmd(json_output: bool = _json_flag()) -> None:
    """Sign in to Canon Cloud via a device code. Local Canon still works without this."""
    console = _use_json(json_output)
    client = CloudClient()
    started = client.start_device()
    user_code = str(started.get("user_code") or "")
    verify_url = str(started.get("verify_url") or "")
    device_code = str(started.get("device_code") or "")
    interval = int(started.get("interval") or 2)
    if not user_code or not device_code:
        raise CloudError("Canon Cloud did not return a device code.")
    if console.json_mode:
        console.emit_json(
            {"verify_url": verify_url, "user_code": user_code, "device_code": device_code}
        )
    else:
        console.print("Open this URL and confirm the code:")
        console.print(f"  {verify_url}")
        console.print(f"  Code: {user_code}")
    deadline = time.time() + 300
    while time.time() < deadline:
        time.sleep(max(1, interval))
        polled = client.poll_device(device_code)
        status = str(polled.get("status") or "")
        if status == "pending":
            continue
        if status != "approved":
            raise CloudError("Canon Cloud login was not approved.")
        creds = CloudCredentials(
            base_url=default_base_url(),
            token=str(polled.get("token") or ""),
            email=str(polled.get("email") or ""),
            plan=str(polled.get("plan") or "free"),
            user_id=str(polled.get("user_id") or ""),
        )
        if not creds.token:
            raise CloudError("Canon Cloud did not return a session token.")
        save_credentials(creds)
        if console.json_mode:
            console.emit_json({"ok": True, "email": creds.email, "plan": creds.plan})
            return
        console.print(f"Signed in as {creds.email or creds.user_id} ({creds.plan}).")
        return
    raise CloudError("Canon Cloud login timed out.", "Run `canon cloud login` again.")


@cloud_app.command("logout")
def logout_cmd(json_output: bool = _json_flag()) -> None:
    """Remove local Canon Cloud credentials."""
    console = _use_json(json_output)
    removed = clear_credentials()
    if console.json_mode:
        console.emit_json({"removed": removed})
        return
    console.print("Signed out of Canon Cloud." if removed else "No Canon Cloud session.")


@cloud_app.command("status")
def status_cmd(json_output: bool = _json_flag()) -> None:
    """Show Canon Cloud session, plan, and this project's workspace."""
    console = _use_json(json_output)
    creds = load_credentials()
    runtime = _runtime()
    try:
        workspace = _workspace_slug(runtime.repo)
        payload: dict[str, Any] = {
            "signed_in": creds is not None,
            "base_url": default_base_url(),
            "workspace": workspace,
        }
        if creds is not None:
            me = CloudClient(creds).me()
            payload.update(
                {
                    "email": me.get("email") or creds.email,
                    "plan": me.get("plan") or creds.plan,
                    "user_id": me.get("id") or creds.user_id,
                    "seats": me.get("seats"),
                }
            )
        if console.json_mode:
            console.emit_json(payload)
            return
        if creds is None:
            console.print("Canon Cloud: signed out (local-only).")
            console.print("  canon cloud login")
            return
        console.print(f"Canon Cloud: {payload.get('email') or payload.get('user_id')}")
        console.print(f"Plan:       {payload.get('plan')}")
        console.print(f"Workspace:  {workspace}")
        console.print(f"Server:     {payload['base_url']}")
    finally:
        runtime.close()


@cloud_app.command("push")
def push_cmd(json_output: bool = _json_flag()) -> None:
    """Upload this project's decisions to Canon Cloud. Local copy stays the source of truth until you pull."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        client = CloudClient.from_saved()
        workspace = _workspace_slug(runtime.repo)
        snapshot = runtime.store.export_payload()
        result = client.push(workspace, snapshot)
        if console.json_mode:
            console.emit_json(result)
            return
        console.print(
            f"Pushed {result.get('count', 0)} decision(s) to {result.get('workspace') or workspace}."
        )
    finally:
        runtime.close()


@cloud_app.command("pull")
def pull_cmd(
    overwrite: bool = typer.Option(False, "--overwrite", help="Replace matching fingerprints."),
    json_output: bool = _json_flag(),
) -> None:
    """Download workspace decisions into the local store."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        client = CloudClient.from_saved()
        workspace = _workspace_slug(runtime.repo)
        result = client.pull(workspace)
        snapshot = result.get("snapshot")
        if not isinstance(snapshot, dict):
            raise CloudError("Canon Cloud returned an empty snapshot.")
        count = runtime.service.import_decisions(snapshot, overwrite=overwrite)
        refresh_injection_files(runtime.paths, runtime.store, runtime.repo, runtime.settings)
        if console.json_mode:
            console.emit_json({"imported": count, "workspace": workspace})
            return
        console.print(f"Imported {count} decision(s) from {workspace}.")
    finally:
        runtime.close()


@cloud_app.command("invite")
def invite_cmd(
    email: str = typer.Argument(..., help="Teammate email."),
    json_output: bool = _json_flag(),
) -> None:
    """Invite someone to this project's cloud workspace."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        client = CloudClient.from_saved()
        workspace = _workspace_slug(runtime.repo)
        result = client.invite(workspace, email)
        if console.json_mode:
            console.emit_json(result)
            return
        console.print(f"Invite for {email}: {result.get('code')}")
        console.print("They run:  canon cloud login   then   canon cloud accept <code>")
    finally:
        runtime.close()


@cloud_app.command("accept")
def accept_cmd(
    code: str = typer.Argument(..., help="Invite code."),
    json_output: bool = _json_flag(),
) -> None:
    """Accept a workspace invite."""
    console = _use_json(json_output)
    client = CloudClient.from_saved()
    result = client.accept(code.strip())
    if console.json_mode:
        console.emit_json(result)
        return
    console.print(f"Joined workspace {result.get('workspace')}.")


@cloud_app.command("members")
def members_cmd(json_output: bool = _json_flag()) -> None:
    """List workspace members."""
    console = _use_json(json_output)
    runtime = _runtime()
    try:
        client = CloudClient.from_saved()
        workspace = _workspace_slug(runtime.repo)
        result = client.members(workspace)
        if console.json_mode:
            console.emit_json(result)
            return
        rows = result.get("members") or []
        if not isinstance(rows, list) or not rows:
            console.print("No members.")
            return
        table = []
        for row in rows:
            if isinstance(row, dict):
                table.append(
                    [str(row.get("email") or ""), str(row.get("role") or ""), str(row.get("plan") or "")]
                )
        console.table("Canon Cloud members", ["Email", "Role", "Plan"], table)
    finally:
        runtime.close()


@cloud_app.command("upgrade")
def upgrade_cmd(
    plan: str = typer.Argument("pro", help="pro or team"),
    json_output: bool = _json_flag(),
) -> None:
    """Open a Polar checkout for Pro or Team. Stripe is not used (India invite-only)."""
    console = _use_json(json_output)
    wanted = plan.strip().lower()
    if wanted not in {"pro", "team"}:
        raise UsageError("Plan must be pro or team.")
    client = CloudClient.from_saved()
    result = client.checkout(wanted)
    url = str(result.get("url") or "")
    if console.json_mode:
        console.emit_json(result)
        return
    if not url:
        raise CloudError(
            "Canon Cloud could not start checkout.",
            "Polar is not configured on the server, or your plan is already active.",
        )
    console.print(f"Pay with Polar ({wanted}):")
    console.print(f"  {url}")
