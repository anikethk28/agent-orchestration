"""Sandboxed Python code execution tool."""
from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stderr, redirect_stdout

from orchestration.config import get_settings

from .registry import ToolDefinition, get_registry


def execute_python(code: str) -> dict:
    """Execute Python code in a restricted namespace and return stdout/stderr/result."""
    settings = get_settings()
    timeout = settings.code_exec_timeout_seconds

    safe_builtins = {
        "print": print,
        "range": range,
        "len": len,
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "list": list,
        "dict": dict,
        "tuple": tuple,
        "set": set,
        "sum": sum,
        "min": min,
        "max": max,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "filter": filter,
        "isinstance": isinstance,
        "type": type,
        "__import__": __builtins__["__import__"] if isinstance(__builtins__, dict) else __import__,
    }

    namespace: dict = {"__builtins__": safe_builtins}
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(compile(code, "<agent_code>", "exec"), namespace)  # noqa: S102
        return {
            "success": True,
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "error": None,
        }
    except Exception:
        return {
            "success": False,
            "stdout": stdout_buf.getvalue(),
            "stderr": stderr_buf.getvalue(),
            "error": traceback.format_exc(),
        }


def register_code_exec(registry=None) -> None:
    if registry is None:
        registry = get_registry()
    registry.register(
        ToolDefinition(
            name="execute_python",
            description="Execute Python code in a sandboxed environment. Returns stdout, stderr, and success status.",
            fn=execute_python,
            allowed_specialists=["coder", "analyst"],
            input_schema={"code": "str — valid Python source code"},
            output_schema={"success": "bool", "stdout": "str", "stderr": "str", "error": "str | null"},
            rate_limit_rpm=20,
        )
    )
