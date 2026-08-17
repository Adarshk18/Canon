from __future__ import annotations

from typing import Any
from urllib.parse import quote

from canon.cloud.credentials import CloudCredentials, default_base_url, load_credentials
from canon.cloud.http import request_json
from canon.errors import CloudError, UsageError


class CloudClient:
    def __init__(
        self,
        creds: CloudCredentials | None = None,
        *,
        base_url: str | None = None,
    ) -> None:
        self.creds = creds
        self.base_url = (base_url or (creds.base_url if creds else default_base_url())).rstrip("/")

    @classmethod
    def from_saved(cls) -> CloudClient:
        creds = load_credentials()
        if creds is None:
            raise UsageError(
                "Not signed in to Canon Cloud.",
                "Run:\n\n    canon cloud login\n",
            )
        return cls(creds)

    def start_device(self) -> dict[str, Any]:
        return request_json("POST", f"{self.base_url}/v1/device/start")

    def poll_device(self, device_code: str) -> dict[str, Any]:
        return request_json(
            "POST",
            f"{self.base_url}/v1/device/poll",
            payload={"device_code": device_code},
        )

    def me(self) -> dict[str, Any]:
        return self._auth("GET", "/v1/me")

    def checkout(self, plan: str) -> dict[str, Any]:
        return self._auth("POST", "/v1/billing/checkout", {"plan": plan})

    def push(self, workspace: str, snapshot: dict[str, Any]) -> dict[str, Any]:
        return self._auth(
            "PUT", f"/v1/workspaces/{_slug(workspace)}/snapshot", {"snapshot": snapshot}
        )

    def pull(self, workspace: str) -> dict[str, Any]:
        return self._auth("GET", f"/v1/workspaces/{_slug(workspace)}/snapshot")

    def invite(self, workspace: str, email: str) -> dict[str, Any]:
        return self._auth("POST", f"/v1/workspaces/{_slug(workspace)}/invites", {"email": email})

    def accept(self, code: str) -> dict[str, Any]:
        return self._auth("POST", "/v1/invites/accept", {"code": code})

    def members(self, workspace: str) -> dict[str, Any]:
        return self._auth("GET", f"/v1/workspaces/{_slug(workspace)}/members")

    def _auth(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        if self.creds is None:
            raise CloudError("Missing Canon Cloud credentials.")
        return request_json(
            method,
            f"{self.base_url}{path}",
            token=self.creds.token,
            payload=payload,
        )


def _slug(workspace: str) -> str:
    return quote(workspace, safe="")
