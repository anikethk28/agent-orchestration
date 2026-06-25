"""Base agent class shared by Supervisor, Specialists, and Reviewer."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from orchestration.config import get_settings
from orchestration.graph.state import AgentState, TraceEvent

log = structlog.get_logger()


def _build_llm(model: str):
    settings = get_settings()
    if model.startswith("claude"):
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=0,
            max_tokens=4096,
        )
    return ChatOpenAI(
        model=model,
        api_key=settings.openai_api_key,
        temperature=0,
        max_tokens=4096,
    )


class BaseAgent(ABC):
    name: str = "base"

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self.model_name = model or settings.specialist_model
        self.llm = _build_llm(self.model_name)
        self.log = structlog.get_logger(agent=self.name)

    def _emit_trace(self, state: AgentState, event_type: str, data: dict[str, Any], latency_ms: float = 0.0) -> None:
        event = TraceEvent(
            task_id=state.task_id,
            agent=self.name,
            event_type=event_type,
            data=data,
            latency_ms=latency_ms,
        )
        state.trace_events.append(event)

    def _invoke_llm(self, messages: list, state: AgentState) -> Any:
        start = time.perf_counter()
        response = self.llm.invoke(messages)
        latency_ms = (time.perf_counter() - start) * 1000

        usage = getattr(response, "usage_metadata", None)
        tokens = 0
        if usage:
            tokens = usage.get("total_tokens", 0)
            state.total_tokens += tokens

        self._emit_trace(
            state,
            "llm_call",
            {"model": self.model_name, "tokens": tokens, "response_preview": str(response.content)[:200]},
            latency_ms=latency_ms,
        )
        return response

    @abstractmethod
    def run(self, state: AgentState) -> AgentState:
        """Execute agent logic and return updated state."""
