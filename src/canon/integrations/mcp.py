"""Minimal stdio MCP server. No extra dependency. Local lookup only."""

from __future__ import annotations

import json
import sys
from typing import Any

from canon import PRODUCT_NAME, __version__
from canon.core.models import DecisionStatus
from canon.errors import CanonError, NotInitializedError, UsageError
from canon.integrations.snapshot import select_for_injection
from canon.runtime import load_runtime

PROTOCOL = "2024-11-05"


def _tools() -> list[dict[str, Any]]:
    return [
        {
            "name": "canon_list",
            "description": (
                "List Canon decisions. Default: active only. "
                "These are human-confirmed. Not vendor auto-memory."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "description": "active | candidate | rejected | superseded | all",
                    }
                },
            },
        },
        {
            "name": "canon_show",
            "description": "Show one Canon decision including provenance.",
            "inputSchema": {
                "type": "object",
                "properties": {"id": {"type": "integer"}},
                "required": ["id"],
            },
        },
        {
            "name": "canon_query",
            "description": "Find relevant active Canon decisions for a question or file path.",
            "inputSchema": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
        {
            "name": "canon_inject",
            "description": "Return the exact text Canon would inject into an agent session.",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def _content(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _call_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        runtime = load_runtime(require_init=True)
    except (NotInitializedError, CanonError) as exc:
        return _error(str(exc))
    try:
        if name == "canon_list":
            status = str(arguments.get("status") or "active").strip().lower()
            if status == "all":
                statuses = list(DecisionStatus)
            else:
                try:
                    statuses = [DecisionStatus(status)]
                except ValueError:
                    return _error("status must be active, candidate, rejected, superseded, or all.")
            rows = runtime.service.list_decisions(statuses=statuses)
            lines = [
                f"#{item.id}  {item.status.value.upper()}  {item.title}" for item in rows
            ]
            return _content("\n".join(lines) if lines else "No decisions match.")
        if name == "canon_show":
            ident = arguments.get("id")
            if not isinstance(ident, int):
                return _error("id must be an integer.")
            item = runtime.service.get(ident)
            parts = [
                f"Decision #{item.id}",
                f"Status: {item.status.value.upper()}",
                item.title,
                "",
                item.body,
                "",
                *item.provenance_lines(),
            ]
            return _content("\n".join(parts))
        if name == "canon_query":
            query = str(arguments.get("query") or "").strip()
            if not query:
                return _error("query is required.")
            _selected, _stats, text = select_for_injection(
                runtime.store, runtime.repo, runtime.settings, query=query
            )
            return _content(text)
        if name == "canon_inject":
            _selected, _stats, text = select_for_injection(
                runtime.store, runtime.repo, runtime.settings
            )
            return _content(text)
        return _error(f"Unknown tool: {name}")
    except UsageError as exc:
        return _error(exc.message)
    finally:
        runtime.close()


def handle_request(message: dict[str, Any]) -> dict[str, Any] | None:
    method = str(message.get("method") or "")
    ident = message.get("id")
    raw_params = message.get("params")
    params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": ident,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": PRODUCT_NAME.lower(), "version": __version__},
            },
        }
    if method in {"notifications/initialized", "initialized"}:
        return None
    if ident is None:
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": ident, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": ident, "result": {"tools": _tools()}}
    if method == "tools/call":
        name = str(params.get("name") or "")
        raw_arguments = params.get("arguments")
        arguments: dict[str, Any] = raw_arguments if isinstance(raw_arguments, dict) else {}
        result = _call_tool(name, arguments)
        return {"jsonrpc": "2.0", "id": ident, "result": result}
    return {
        "jsonrpc": "2.0",
        "id": ident,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def _read_message() -> dict[str, Any] | None:
    buf = sys.stdin.buffer
    first = buf.readline()
    if not first:
        return None
    stripped = first.lstrip()
    if stripped.startswith(b"{"):
        loaded = json.loads(stripped.decode("utf-8"))
        return loaded if isinstance(loaded, dict) else None
    headers = first.decode("utf-8")
    while True:
        line = buf.readline()
        if not line or line in {b"\n", b"\r\n"}:
            break
        headers += line.decode("utf-8")
    length = 0
    for raw in headers.splitlines():
        if raw.lower().startswith("content-length:"):
            length = int(raw.split(":", 1)[1].strip())
    if length <= 0:
        return None
    body = buf.read(length)
    loaded = json.loads(body.decode("utf-8"))
    return loaded if isinstance(loaded, dict) else None


def _write_message(payload: dict[str, Any]) -> None:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(data)}\r\n\r\n".encode("ascii"))
    sys.stdout.buffer.write(data)
    sys.stdout.buffer.flush()


def run_stdio() -> None:
    while True:
        try:
            message = _read_message()
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            break
        if message is None:
            break
        reply = handle_request(message)
        if reply is not None:
            _write_message(reply)
