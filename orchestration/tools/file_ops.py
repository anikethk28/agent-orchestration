"""File read/write tools — scoped to a sandboxed workspace directory."""
from __future__ import annotations

import os
from pathlib import Path

from .registry import ToolDefinition, get_registry

WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_DIR", "/tmp/agent_workspace")).resolve()
WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)


def _safe_path(filename: str) -> Path:
    """Resolve path inside workspace; reject traversal attempts."""
    resolved = (WORKSPACE_ROOT / filename).resolve()
    if not str(resolved).startswith(str(WORKSPACE_ROOT)):
        raise ValueError(f"Path traversal blocked: {filename}")
    return resolved


def file_read(filename: str) -> str:
    path = _safe_path(filename)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {filename}")
    return path.read_text()


def file_write(filename: str, content: str) -> dict:
    path = _safe_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return {"filename": filename, "bytes_written": len(content.encode())}


def file_list(directory: str = "") -> list[str]:
    base = _safe_path(directory) if directory else WORKSPACE_ROOT
    if not base.is_dir():
        return []
    return [str(p.relative_to(WORKSPACE_ROOT)) for p in base.rglob("*") if p.is_file()]


def register_file_ops(registry=None) -> None:
    if registry is None:
        registry = get_registry()
    for tool in [
        ToolDefinition(
            name="file_read",
            description="Read the contents of a file from the workspace.",
            fn=file_read,
            allowed_specialists=["researcher", "analyst", "writer", "coder"],
            input_schema={"filename": "str"},
            output_schema={"content": "str"},
        ),
        ToolDefinition(
            name="file_write",
            description="Write content to a file in the workspace.",
            fn=file_write,
            allowed_specialists=["writer", "coder", "analyst"],
            input_schema={"filename": "str", "content": "str"},
            output_schema={"filename": "str", "bytes_written": "int"},
        ),
        ToolDefinition(
            name="file_list",
            description="List files in the workspace directory.",
            fn=file_list,
            allowed_specialists=["researcher", "analyst", "writer", "coder"],
            input_schema={"directory": "str (optional, defaults to root)"},
            output_schema={"files": "list[str]"},
        ),
    ]:
        registry.register(tool)
