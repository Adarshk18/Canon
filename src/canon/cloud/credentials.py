from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from canon.config.paths import user_home
from canon.security.paths import resolve_path

CREDENTIALS_NAME = "credentials.toml"


def credentials_path() -> Path:
    override = os.environ.get("CANON_CLOUD_CREDENTIALS")
    if override:
        return resolve_path(Path(override))
    return user_home() / CREDENTIALS_NAME


@dataclass(slots=True)
class CloudCredentials:
    base_url: str
    token: str
    email: str
    plan: str
    user_id: str

    def to_toml(self) -> str:
        return (
            "# Canon Cloud credentials. Do not commit.\n"
            f'base_url = "{_escape(self.base_url)}"\n'
            f'token = "{_escape(self.token)}"\n'
            f'email = "{_escape(self.email)}"\n'
            f'plan = "{_escape(self.plan)}"\n'
            f'user_id = "{_escape(self.user_id)}"\n'
        )


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def load_credentials() -> CloudCredentials | None:
    path = credentials_path()
    if not path.is_file():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    token = str(data.get("token") or "")
    if not token:
        return None
    return CloudCredentials(
        base_url=str(data.get("base_url") or default_base_url()).rstrip("/"),
        token=token,
        email=str(data.get("email") or ""),
        plan=str(data.get("plan") or "free"),
        user_id=str(data.get("user_id") or ""),
    )


def save_credentials(creds: CloudCredentials) -> Path:
    path = credentials_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(creds.to_toml(), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def clear_credentials() -> bool:
    path = credentials_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def default_base_url() -> str:
    return os.environ.get("CANON_CLOUD_URL", "http://127.0.0.1:8787").rstrip("/")
