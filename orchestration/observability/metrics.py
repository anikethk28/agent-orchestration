"""Cost and performance tracking for agent executions."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import structlog

log = structlog.get_logger()

# Approximate cost per 1M tokens (input/output averaged)
MODEL_COSTS: dict[str, float] = {
    "claude-sonnet-4-6": 3.75,
    "claude-haiku-4-5-20251001": 0.4,
    "gpt-4o-mini": 0.3,
    "gpt-4o": 5.0,
}


@dataclass
class TaskMetrics:
    task_id: str
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None
    tokens_by_agent: dict[str, int] = field(default_factory=dict)
    tool_calls_by_agent: dict[str, int] = field(default_factory=dict)
    cost_by_agent: dict[str, float] = field(default_factory=dict)
    human_review_time_seconds: float = 0.0
    escalation_count: int = 0

    @property
    def total_tokens(self) -> int:
        return sum(self.tokens_by_agent.values())

    @property
    def total_cost_usd(self) -> float:
        return sum(self.cost_by_agent.values())

    @property
    def wall_clock_seconds(self) -> float:
        end = self.completed_at or datetime.utcnow()
        return (end - self.started_at).total_seconds()

    def record_llm_call(self, agent: str, model: str, tokens: int) -> None:
        self.tokens_by_agent[agent] = self.tokens_by_agent.get(agent, 0) + tokens
        cost_per_million = MODEL_COSTS.get(model, 1.0)
        call_cost = (tokens / 1_000_000) * cost_per_million
        self.cost_by_agent[agent] = self.cost_by_agent.get(agent, 0.0) + call_cost

    def record_tool_call(self, agent: str) -> None:
        self.tool_calls_by_agent[agent] = self.tool_calls_by_agent.get(agent, 0) + 1

    def complete(self) -> None:
        self.completed_at = datetime.utcnow()
        log.info(
            "task_metrics",
            task_id=self.task_id,
            wall_clock_s=self.wall_clock_seconds,
            total_tokens=self.total_tokens,
            total_cost_usd=round(self.total_cost_usd, 6),
            escalations=self.escalation_count,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "wall_clock_seconds": self.wall_clock_seconds,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "tokens_by_agent": self.tokens_by_agent,
            "tool_calls_by_agent": self.tool_calls_by_agent,
            "cost_by_agent": {k: round(v, 6) for k, v in self.cost_by_agent.items()},
            "human_review_time_seconds": self.human_review_time_seconds,
            "escalation_count": self.escalation_count,
        }


_task_metrics_store: dict[str, TaskMetrics] = {}


def start_task_metrics(task_id: str) -> TaskMetrics:
    m = TaskMetrics(task_id=task_id)
    _task_metrics_store[task_id] = m
    return m


def get_task_metrics(task_id: str) -> TaskMetrics | None:
    return _task_metrics_store.get(task_id)


def aggregate_metrics() -> dict[str, Any]:
    all_metrics = list(_task_metrics_store.values())
    if not all_metrics:
        return {}
    return {
        "total_tasks": len(all_metrics),
        "total_cost_usd": round(sum(m.total_cost_usd for m in all_metrics), 4),
        "total_tokens": sum(m.total_tokens for m in all_metrics),
        "avg_wall_clock_seconds": sum(m.wall_clock_seconds for m in all_metrics) / len(all_metrics),
        "escalation_rate": sum(1 for m in all_metrics if m.escalation_count > 0) / len(all_metrics),
    }
