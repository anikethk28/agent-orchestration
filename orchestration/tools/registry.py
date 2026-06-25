"""Central tool registry — register, discover, and invoke tools with logging."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable

import structlog

log = structlog.get_logger()


@dataclass
class ToolInvocation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    tool_name: str = ""
    agent: str = ""
    inputs: dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ToolDefinition:
    name: str
    description: str
    fn: Callable
    allowed_specialists: list[str]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    rate_limit_rpm: int = 60
    _call_timestamps: list[datetime] = field(default_factory=list, repr=False)

    def is_rate_limited(self) -> bool:
        now = datetime.utcnow()
        cutoff = now - timedelta(minutes=1)
        self._call_timestamps = [t for t in self._call_timestamps if t > cutoff]
        return len(self._call_timestamps) >= self.rate_limit_rpm

    def record_call(self) -> None:
        self._call_timestamps.append(datetime.utcnow())


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._invocation_log: list[ToolInvocation] = []

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool
        log.info("tool_registered", name=tool.name)

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def list_for_specialist(self, specialist: str) -> list[ToolDefinition]:
        return [t for t in self._tools.values() if specialist in t.allowed_specialists]

    def invoke(self, name: str, agent: str, **kwargs: Any) -> Any:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Tool '{name}' not found in registry")

        if tool.is_rate_limited():
            raise RuntimeError(f"Tool '{name}' is rate limited ({tool.rate_limit_rpm} rpm)")

        invocation = ToolInvocation(tool_name=name, agent=agent, inputs=kwargs)
        start = time.perf_counter()
        try:
            tool.record_call()
            result = tool.fn(**kwargs)
            invocation.output = result
            invocation.success = True
            log.info("tool_invoked", tool=name, agent=agent, success=True)
            return result
        except Exception as exc:
            invocation.error = str(exc)
            invocation.success = False
            log.error("tool_error", tool=name, agent=agent, error=str(exc))
            raise
        finally:
            invocation.latency_ms = (time.perf_counter() - start) * 1000
            self._invocation_log.append(invocation)

    def get_invocation_log(self, tool_name: str | None = None) -> list[ToolInvocation]:
        if tool_name:
            return [i for i in self._invocation_log if i.tool_name == tool_name]
        return list(self._invocation_log)

    def get_stats(self) -> dict[str, Any]:
        stats: dict[str, dict] = defaultdict(lambda: {"calls": 0, "failures": 0, "total_latency_ms": 0.0})
        for inv in self._invocation_log:
            s = stats[inv.tool_name]
            s["calls"] += 1
            s["total_latency_ms"] += inv.latency_ms
            if not inv.success:
                s["failures"] += 1
        return {
            name: {
                **s,
                "avg_latency_ms": s["total_latency_ms"] / s["calls"] if s["calls"] else 0,
                "success_rate": 1 - s["failures"] / s["calls"] if s["calls"] else 1,
            }
            for name, s in stats.items()
        }


# Singleton registry
_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry
