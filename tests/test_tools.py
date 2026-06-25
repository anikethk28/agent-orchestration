"""Tests for the tool registry and individual tools."""
import pytest
from unittest.mock import patch

from orchestration.tools.registry import ToolDefinition, ToolRegistry
from orchestration.tools.code_exec import execute_python
from orchestration.tools.file_ops import file_read, file_write, file_list


# ── Registry ─────────────────────────────────────────────────────────────────

def test_tool_registration():
    reg = ToolRegistry()
    tool = ToolDefinition(
        name="test_tool",
        description="A test tool",
        fn=lambda x: x,
        allowed_specialists=["researcher"],
        input_schema={"x": "str"},
        output_schema={"result": "str"},
    )
    reg.register(tool)
    assert reg.get("test_tool") is not None


def test_specialist_tool_filter():
    reg = ToolRegistry()
    for name, specialists in [("research_tool", ["researcher"]), ("code_tool", ["coder"]), ("shared_tool", ["researcher", "coder"])]:
        reg.register(ToolDefinition(
            name=name, description="", fn=lambda: None,
            allowed_specialists=specialists, input_schema={}, output_schema={},
        ))

    researcher_tools = {t.name for t in reg.list_for_specialist("researcher")}
    assert "research_tool" in researcher_tools
    assert "shared_tool" in researcher_tools
    assert "code_tool" not in researcher_tools


def test_unknown_tool_raises():
    reg = ToolRegistry()
    with pytest.raises(ValueError, match="not found"):
        reg.invoke("nonexistent_tool", agent="test")


def test_invocation_logging():
    reg = ToolRegistry()
    reg.register(ToolDefinition(
        name="echo", description="", fn=lambda msg: msg,
        allowed_specialists=["researcher"], input_schema={}, output_schema={},
    ))
    reg.invoke("echo", agent="researcher", msg="hello")
    log = reg.get_invocation_log("echo")
    assert len(log) == 1
    assert log[0].success is True
    assert log[0].output == "hello"


# ── Code execution ────────────────────────────────────────────────────────────

def test_execute_python_success():
    result = execute_python("x = 2 + 2\nprint(x)")
    assert result["success"] is True
    assert "4" in result["stdout"]


def test_execute_python_captures_error():
    result = execute_python("raise ValueError('oops')")
    assert result["success"] is False
    assert "ValueError" in result["error"]


def test_execute_python_blocks_dangerous_builtins():
    result = execute_python("import subprocess; subprocess.run(['ls'])")
    # Should either fail or be blocked
    assert result["success"] is False or "subprocess" in result.get("error", "")


# ── File operations ───────────────────────────────────────────────────────────

def test_file_write_and_read(tmp_path, monkeypatch):
    import orchestration.tools.file_ops as fops
    monkeypatch.setattr(fops, "WORKSPACE_ROOT", tmp_path)

    write_result = file_write("test.txt", "hello world")
    assert write_result["bytes_written"] > 0

    content = file_read("test.txt")
    assert content == "hello world"


def test_file_path_traversal_blocked(tmp_path, monkeypatch):
    import orchestration.tools.file_ops as fops
    monkeypatch.setattr(fops, "WORKSPACE_ROOT", tmp_path)

    with pytest.raises(ValueError, match="traversal"):
        file_read("../../../etc/passwd")
