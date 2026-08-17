from __future__ import annotations

import os

from canon.server.app import create_app


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:
        raise SystemExit(
            "Install the server extra:\n\n    pip install 'canon-memory[server]'\n"
        ) from exc
    host = os.environ.get("CANON_CLOUD_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT") or os.environ.get("CANON_CLOUD_PORT", "8787"))
    uvicorn.run(create_app(), host=host, port=port)


if __name__ == "__main__":
    main()
