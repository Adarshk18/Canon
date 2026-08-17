from __future__ import annotations

from pathlib import Path

from canon.cloud.credentials import (
    CloudCredentials,
    clear_credentials,
    load_credentials,
    save_credentials,
)


def test_save_and_load_credentials(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.setenv("CANON_CLOUD_CREDENTIALS", str(tmp_path / "creds.toml"))  # type: ignore[attr-defined]
    saved = CloudCredentials(
        base_url="http://127.0.0.1:8787",
        token="tok_test",
        email="dev@example.com",
        plan="pro",
        user_id="abc",
    )
    save_credentials(saved)
    loaded = load_credentials()
    assert loaded is not None
    assert loaded.token == "tok_test"
    assert loaded.email == "dev@example.com"
    assert clear_credentials() is True
    assert load_credentials() is None
