"""Escalation logic — determines when and how to involve a human reviewer."""
from __future__ import annotations

from orchestration.config import get_settings
from orchestration.graph.state import AgentState, EscalationLevel, HumanReviewRequest, TaskStatus

SENSITIVE_KEYWORDS = frozenset([
    "delete", "drop", "truncate", "payment", "transfer", "money", "bank",
    "credential", "password", "secret", "send email", "send message", "publish",
    "deploy", "production", "billing",
])


def should_escalate(state: AgentState) -> tuple[bool, EscalationLevel | None, str]:
    """Return (should_escalate, level, reason)."""
    settings = get_settings()
    request_lower = state.original_request.lower()

    # Sensitive operation check
    if any(kw in request_lower for kw in SENSITIVE_KEYWORDS):
        return True, EscalationLevel.APPROVE_ACTION, "Task contains sensitive operations requiring explicit approval"

    # Low plan confidence
    if state.plan_confidence < settings.hitl_confidence_threshold:
        return True, EscalationLevel.APPROVE_PLAN, f"Plan confidence {state.plan_confidence:.2f} below threshold"

    # Output quality below threshold
    if state.current_output_quality < settings.hitl_confidence_threshold:
        return True, EscalationLevel.APPROVE_ACTION, f"Output quality {state.current_output_quality:.2f} too low"

    return False, None, ""


def build_review_request(
    state: AgentState,
    level: EscalationLevel,
    reason: str,
    proposed_action: str = "",
    agent_reasoning: str = "",
) -> HumanReviewRequest:
    context: dict = {"original_request": state.original_request}
    if state.plan:
        context["plan_summary"] = {
            "subtask_count": len(state.plan.subtasks),
            "confidence": state.plan.confidence,
            "reasoning": state.plan.reasoning,
        }
    if state.subtask_outputs:
        context["completed_subtasks"] = len(state.subtask_outputs)

    return HumanReviewRequest(
        task_id=state.task_id,
        level=level,
        trigger_reason=reason,
        context=context,
        proposed_action=proposed_action or "Continue with current plan",
        agent_reasoning=agent_reasoning or state.plan.reasoning if state.plan else "",
    )


def apply_human_resolution(state: AgentState, resolution: str, approved: bool, notes: str = "") -> AgentState:
    """Update state after a human makes a decision."""
    if state.pending_review:
        from datetime import datetime
        state.pending_review.resolved_at = datetime.utcnow()
        state.pending_review.resolution = resolution
        state.pending_review.reviewer_notes = notes

    state.human_approved = approved

    if not approved:
        state.status = TaskStatus.FAILED
        state.error = f"Human reviewer rejected: {notes}"
    else:
        # Resume from where we paused
        if state.status == TaskStatus.AWAITING_HUMAN:
            if state.plan and state.plan_confidence < get_settings().hitl_confidence_threshold:
                state.status = TaskStatus.EXECUTING
            else:
                state.status = TaskStatus.EXECUTING

    state.pending_review = None
    return state
