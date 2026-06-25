"""Tests that the Reviewer correctly scores and routes outputs."""
import json
import pytest
from unittest.mock import MagicMock, patch

from orchestration.agents.reviewer import ReviewerAgent
from orchestration.graph.state import (
    AgentState,
    ExecutionPlan,
    SpecialistType,
    Subtask,
    SubtaskStatus,
    TaskStatus,
)


def _make_state(output_quality: str = "good") -> AgentState:
    subtask = Subtask(
        id="sub-1",
        description="Research quantum computing",
        specialist=SpecialistType.RESEARCHER,
        expected_output_format="Bulleted list",
        status=SubtaskStatus.COMPLETED,
    )
    plan = ExecutionPlan(
        original_task="Research quantum computing",
        subtasks=[subtask],
        confidence=0.9,
    )
    state = AgentState(
        task_id="review-test",
        original_request="Research quantum computing",
        plan=plan,
    )
    state.subtask_outputs["sub-1"] = (
        "• Quantum computing uses qubits\n• Key players: IBM, Google, IonQ\n• Current state: NISQ era"
        if output_quality == "good"
        else "I don't know."
    )
    return state


@patch("orchestration.agents.reviewer.ReviewerAgent._invoke_llm")
def test_good_output_passes(mock_llm):
    mock_response = MagicMock()
    mock_response.content = json.dumps({"quality_score": 0.92, "passed": True, "feedback": "", "issues": []})
    mock_llm.return_value = mock_response

    agent = ReviewerAgent.__new__(ReviewerAgent)
    agent.name = "reviewer"
    agent.model_name = "test"
    agent.log = MagicMock()

    state = _make_state("good")
    updated = agent.run(state)

    assert updated.status == TaskStatus.REVIEWING


@patch("orchestration.agents.reviewer.ReviewerAgent._invoke_llm")
def test_poor_output_rejected_for_retry(mock_llm):
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "quality_score": 0.65, "passed": False,
        "feedback": "Too vague, needs specific examples", "issues": ["lacks detail"]
    })
    mock_llm.return_value = mock_response

    agent = ReviewerAgent.__new__(ReviewerAgent)
    agent.name = "reviewer"
    agent.model_name = "test"
    agent.log = MagicMock()

    state = _make_state("bad")
    updated = agent.run(state)

    assert updated.plan.subtasks[0].status == SubtaskStatus.PENDING
    assert updated.plan.subtasks[0].reviewer_feedback is not None


@patch("orchestration.agents.reviewer.ReviewerAgent._invoke_llm")
def test_critically_bad_output_escalates(mock_llm):
    mock_response = MagicMock()
    mock_response.content = json.dumps({
        "quality_score": 0.2, "passed": False,
        "feedback": "Completely wrong", "issues": ["hallucination"]
    })
    mock_llm.return_value = mock_response

    agent = ReviewerAgent.__new__(ReviewerAgent)
    agent.name = "reviewer"
    agent.model_name = "test"
    agent.log = MagicMock()

    state = _make_state("bad")
    updated = agent.run(state)

    assert updated.status == TaskStatus.AWAITING_HUMAN
    assert updated.pending_review is not None
