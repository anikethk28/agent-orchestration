"""Reviewer Agent — validates specialist outputs before synthesis."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from orchestration.config import get_settings
from orchestration.graph.state import (
    AgentState,
    EscalationLevel,
    HumanReviewRequest,
    SubtaskStatus,
    TaskStatus,
)

from .base import BaseAgent

REVIEWER_SYSTEM_PROMPT = """You are a Reviewer Agent. Your job is to evaluate the quality of a specialist agent's output.

Assess the output against:
1. Does it fully address the subtask description?
2. Is the format correct?
3. Is the information accurate and well-supported?
4. Is it free from obvious hallucinations or fabrications?

Respond with valid JSON only:
{
  "quality_score": <float 0.0-1.0>,
  "passed": <bool>,
  "feedback": "<specific, actionable feedback if rejected, else empty string>",
  "issues": ["<list of specific issues if any>"]
}

Scoring guide:
- 0.9-1.0: Excellent — publish as-is
- 0.7-0.89: Good — minor issues, pass
- 0.5-0.69: Poor — needs revision, reject
- 0.0-0.49: Unacceptable — reject
"""


class ReviewerAgent(BaseAgent):
    name = "reviewer"
    QUALITY_THRESHOLD = 0.7
    HITL_THRESHOLD = 0.5

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(model=settings.reviewer_model)

    def run(self, state: AgentState) -> AgentState:
        if state.plan is None:
            return state

        all_passed = True
        for subtask in state.plan.subtasks:
            if subtask.status != SubtaskStatus.COMPLETED:
                continue
            if subtask.id not in state.subtask_outputs:
                continue

            result = self._review_subtask(subtask, state)
            quality = result.get("quality_score", 0.0)
            passed = result.get("passed", False)
            feedback = result.get("feedback", "")

            self._emit_trace(
                state,
                "review_result",
                {"subtask_id": subtask.id, "quality": quality, "passed": passed, "feedback": feedback},
            )

            if not passed:
                all_passed = False
                subtask.reviewer_feedback = feedback
                subtask.status = SubtaskStatus.REJECTED

                if quality < self.HITL_THRESHOLD:
                    state.pending_review = HumanReviewRequest(
                        task_id=state.task_id,
                        level=EscalationLevel.APPROVE_ACTION,
                        trigger_reason=f"Output quality score {quality:.2f} critically low",
                        context={
                            "subtask_id": subtask.id,
                            "subtask_description": subtask.description,
                            "output": state.subtask_outputs[subtask.id][:1000],
                            "issues": result.get("issues", []),
                        },
                        proposed_action="Re-run subtask with reviewer feedback",
                        agent_reasoning=f"Quality {quality:.2f} below critical threshold {self.HITL_THRESHOLD}",
                    )
                    state.status = TaskStatus.AWAITING_HUMAN
                    return state

                subtask.status = SubtaskStatus.PENDING
                subtask.retry_count += 1

        if all_passed:
            state.status = TaskStatus.REVIEWING
            self.log.info("all_subtasks_passed", task_id=state.task_id)

        return state

    def _review_subtask(self, subtask, state: AgentState) -> dict:
        output = state.subtask_outputs.get(subtask.id, "")
        messages = [
            SystemMessage(content=REVIEWER_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Subtask: {subtask.description}\n"
                    f"Expected format: {subtask.expected_output_format}\n\n"
                    f"Specialist output:\n{output}"
                )
            ),
        ]
        response = self._invoke_llm(messages, state)
        raw = response.content.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            self.log.warning("reviewer_parse_error", raw=raw[:200])
            return {"quality_score": 0.5, "passed": True, "feedback": "", "issues": []}
