"""Tests for human-in-the-loop escalation logic."""
import pytest
from unittest.mock import MagicMock, patch

from orchestration.graph.state import AgentState, EscalationLevel, TaskStatus
from orchestration.hitl.escalation import apply_human_resolution, should_escalate


def _base_state(**kwargs) -> AgentState:
    return AgentState(task_id="hitl-test", original_request="test", **kwargs)


def test_sensitive_keyword_triggers_escalation():
    state = _base_state(original_request="delete all user records from the database")
    escalate, level, reason = should_escalate(state)
    assert escalate is True
    assert level == EscalationLevel.APPROVE_ACTION


def test_low_confidence_triggers_plan_approval():
    state = _base_state(plan_confidence=0.3)
    escalate, level, reason = should_escalate(state)
    assert escalate is True
    assert level == EscalationLevel.APPROVE_PLAN


def test_high_confidence_safe_request_no_escalation():
    state = _base_state(
        original_request="Summarize recent AI research papers",
        plan_confidence=0.95,
        current_output_quality=0.85,
    )
    escalate, level, reason = should_escalate(state)
    assert escalate is False


def test_human_approval_resumes_task():
    state = _base_state(status=TaskStatus.AWAITING_HUMAN, plan_confidence=0.95)
    updated = apply_human_resolution(state, resolution="Looks good", approved=True, notes="Approved by admin")
    assert updated.human_approved is True
    assert updated.status == TaskStatus.EXECUTING
    assert updated.pending_review is None


def test_human_rejection_fails_task():
    state = _base_state(status=TaskStatus.AWAITING_HUMAN)
    updated = apply_human_resolution(state, resolution="Too risky", approved=False, notes="Sensitive data involved")
    assert updated.human_approved is False
    assert updated.status == TaskStatus.FAILED
    assert "rejected" in (updated.error or "").lower()
