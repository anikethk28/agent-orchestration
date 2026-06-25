"""Shared state schema for the LangGraph agent workflow."""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage


class TaskStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    AWAITING_HUMAN = "awaiting_human"
    COMPLETED = "completed"
    FAILED = "failed"


class SubtaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"


class EscalationLevel(str, Enum):
    NOTIFY = "notify"
    APPROVE_ACTION = "approve_action"
    APPROVE_PLAN = "approve_plan"
    TAKE_OVER = "take_over"


class SpecialistType(str, Enum):
    RESEARCHER = "researcher"
    ANALYST = "analyst"
    WRITER = "writer"
    CODER = "coder"


class Subtask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    description: str
    specialist: SpecialistType
    required_inputs: list[str] = Field(default_factory=list)
    expected_output_format: str = ""
    estimated_complexity: str = "medium"
    depends_on: list[str] = Field(default_factory=list)
    status: SubtaskStatus = SubtaskStatus.PENDING
    output: str | None = None
    error: str | None = None
    retry_count: int = 0
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    reviewer_feedback: str | None = None


class ExecutionPlan(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_task: str
    subtasks: list[Subtask]
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class HumanReviewRequest(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    level: EscalationLevel
    trigger_reason: str
    context: dict[str, Any]
    proposed_action: str
    agent_reasoning: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    resolution: str | None = None
    reviewer_notes: str | None = None


class TraceEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_id: str
    agent: str
    event_type: str
    data: dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    latency_ms: float | None = None
    tokens_used: int | None = None
    cost_usd: float | None = None


class AgentState(BaseModel):
    """Complete mutable state passed through the LangGraph workflow."""

    # Core identifiers
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = "default"
    original_request: str = ""

    # Conversation messages (LangGraph reducer)
    messages: Annotated[list[BaseMessage], add_messages] = Field(default_factory=list)

    # Execution plan
    plan: ExecutionPlan | None = None
    current_subtask_index: int = 0

    # Specialist outputs keyed by subtask id
    subtask_outputs: dict[str, str] = Field(default_factory=dict)

    # Final synthesized output
    final_output: str | None = None

    # Status
    status: TaskStatus = TaskStatus.PENDING
    error: str | None = None

    # Confidence scores
    plan_confidence: float = 1.0
    current_output_quality: float = 1.0

    # HITL
    pending_review: HumanReviewRequest | None = None
    human_approved: bool | None = None

    # Memory context injected during planning
    retrieved_memories: list[dict[str, Any]] = Field(default_factory=list)

    # Observability
    trace_events: list[TraceEvent] = Field(default_factory=list)
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

    class Config:
        arbitrary_types_allowed = True
