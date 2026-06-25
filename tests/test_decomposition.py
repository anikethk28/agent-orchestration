"""Tests for task decomposition (supervisor planning)."""
import json
import pytest
from unittest.mock import MagicMock, patch

from orchestration.agents.supervisor import SupervisorAgent
from orchestration.graph.state import AgentState, TaskStatus


VALID_PLAN_JSON = json.dumps({
    "confidence": 0.9,
    "reasoning": "Clear research + writing task",
    "subtasks": [
        {
            "description": "Search for information on quantum computing",
            "specialist": "researcher",
            "required_inputs": ["original_task"],
            "expected_output_format": "Bulleted list of key facts",
            "estimated_complexity": "medium",
            "depends_on": [],
        },
        {
            "description": "Write a summary from research findings",
            "specialist": "writer",
            "required_inputs": ["researcher output"],
            "expected_output_format": "500-word prose summary",
            "estimated_complexity": "low",
            "depends_on": [],
        },
    ],
})


@patch("orchestration.agents.supervisor.SupervisorAgent._invoke_llm")
def test_plan_creates_subtasks(mock_llm):
    mock_response = MagicMock()
    mock_response.content = VALID_PLAN_JSON
    mock_llm.return_value = mock_response

    agent = SupervisorAgent.__new__(SupervisorAgent)
    agent.llm = MagicMock()
    agent.name = "supervisor"
    agent.model_name = "test"
    agent.log = MagicMock()

    state = AgentState(original_request="Tell me about quantum computing", task_id="test-123")
    updated = agent._plan(state)

    assert updated.plan is not None
    assert len(updated.plan.subtasks) == 2
    assert updated.plan.confidence == 0.9
    assert updated.status == TaskStatus.EXECUTING


@patch("orchestration.agents.supervisor.SupervisorAgent._invoke_llm")
def test_low_confidence_triggers_hitl(mock_llm):
    low_conf_plan = json.dumps({
        "confidence": 0.4,
        "reasoning": "Ambiguous request",
        "subtasks": [{"description": "Do something", "specialist": "researcher",
                      "required_inputs": [], "expected_output_format": "text",
                      "estimated_complexity": "low", "depends_on": []}],
    })
    mock_response = MagicMock()
    mock_response.content = low_conf_plan
    mock_llm.return_value = mock_response

    agent = SupervisorAgent.__new__(SupervisorAgent)
    agent.llm = MagicMock()
    agent.name = "supervisor"
    agent.model_name = "test"
    agent.log = MagicMock()

    state = AgentState(original_request="Do something vague", task_id="test-456")
    updated = agent._plan(state)

    assert updated.status == TaskStatus.AWAITING_HUMAN
    assert updated.pending_review is not None


@patch("orchestration.agents.supervisor.SupervisorAgent._invoke_llm")
def test_bad_json_fails_gracefully(mock_llm):
    mock_response = MagicMock()
    mock_response.content = "This is not JSON at all."
    mock_llm.return_value = mock_response

    agent = SupervisorAgent.__new__(SupervisorAgent)
    agent.llm = MagicMock()
    agent.name = "supervisor"
    agent.model_name = "test"
    agent.log = MagicMock()

    state = AgentState(original_request="Some task", task_id="test-789")
    updated = agent._plan(state)

    assert updated.status == TaskStatus.FAILED
    assert updated.error is not None
