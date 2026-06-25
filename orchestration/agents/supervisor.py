"""Supervisor Agent — receives complex tasks, plans, and delegates to specialists."""
from __future__ import annotations

import json

from langchain_core.messages import HumanMessage, SystemMessage

from orchestration.config import get_settings
from orchestration.graph.state import (
    AgentState,
    EscalationLevel,
    ExecutionPlan,
    HumanReviewRequest,
    SpecialistType,
    Subtask,
    TaskStatus,
)

from .base import BaseAgent, _build_llm

PLANNING_SYSTEM_PROMPT = """You are a Supervisor Agent in a multi-agent orchestration system.
Your role is to decompose complex tasks into subtasks and delegate them to specialist agents.

Available specialists:
- researcher: Web search, information gathering, fact-finding
- analyst: Data analysis, pattern recognition, structured extraction
- writer: Content creation, summarization, formatting
- coder: Python execution, algorithmic tasks, data transformation

You must respond with valid JSON matching this schema exactly:
{
  "confidence": <float 0.0-1.0>,
  "reasoning": "<why you structured the plan this way>",
  "subtasks": [
    {
      "description": "<what this subtask does>",
      "specialist": "<researcher|analyst|writer|coder>",
      "required_inputs": ["<list of inputs needed, can reference 'original_task'>"],
      "expected_output_format": "<description of expected output format>",
      "estimated_complexity": "<low|medium|high>",
      "depends_on": ["<subtask index 0-based, if any>"]
    }
  ]
}

Rules:
- Use depends_on to express ordering; parallel subtasks have no dependencies.
- Keep subtasks focused — one clear objective each.
- confidence below 0.6 means the task is ambiguous and may need human approval.
"""

SYNTHESIS_SYSTEM_PROMPT = """You are a Supervisor Agent synthesizing the final answer.
You have the original user request and the outputs from specialist agents.
Produce a clear, well-structured final response that directly addresses the user's request.
Integrate insights from all specialist outputs. Be comprehensive yet concise."""


class SupervisorAgent(BaseAgent):
    name = "supervisor"

    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(model=settings.supervisor_model)

    def run(self, state: AgentState) -> AgentState:
        if state.status == TaskStatus.PENDING:
            return self._plan(state)
        if state.status == TaskStatus.REVIEWING:
            return self._synthesize(state)
        return state

    def _plan(self, state: AgentState) -> AgentState:
        state.status = TaskStatus.PLANNING
        self.log.info("planning_task", task_id=state.task_id)

        memory_context = ""
        if state.retrieved_memories:
            snippets = [f"- {m.get('summary', '')}" for m in state.retrieved_memories[:5]]
            memory_context = "\nRelevant past experience:\n" + "\n".join(snippets)

        messages = [
            SystemMessage(content=PLANNING_SYSTEM_PROMPT),
            HumanMessage(content=f"Task: {state.original_request}{memory_context}\n\nCreate an execution plan."),
        ]

        response = self._invoke_llm(messages, state)

        try:
            raw = response.content.strip()
            # Handle markdown code fences
            if "```json" in raw:
                raw = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                raw = raw.split("```")[1].split("```")[0].strip()

            plan_data = json.loads(raw)
            # Assign stable index-based IDs so depends_on integers can be resolved
            raw_subtasks = plan_data["subtasks"]
            index_to_id = {i: f"subtask-{i}" for i in range(len(raw_subtasks))}
            subtasks = []
            for i, st in enumerate(raw_subtasks):
                deps = [index_to_id[int(d)] for d in st.get("depends_on", []) if str(d).isdigit() or isinstance(d, int)]
                subtasks.append(Subtask(**{**st, "id": index_to_id[i], "depends_on": deps}))
            state.plan = ExecutionPlan(
                original_task=state.original_request,
                subtasks=subtasks,
                confidence=plan_data["confidence"],
                reasoning=plan_data.get("reasoning", ""),
            )
            state.plan_confidence = plan_data["confidence"]
            self.log.info("plan_created", subtask_count=len(subtasks), confidence=state.plan_confidence)
            self._emit_trace(state, "plan_created", {"plan": plan_data})

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            self.log.error("plan_parse_error", error=str(exc), raw=response.content[:500])
            state.error = f"Failed to parse execution plan: {exc}"
            state.status = TaskStatus.FAILED
            return state

        settings = get_settings()
        if state.plan_confidence < settings.hitl_confidence_threshold:
            state.pending_review = HumanReviewRequest(
                task_id=state.task_id,
                level=EscalationLevel.APPROVE_PLAN,
                trigger_reason=f"Plan confidence {state.plan_confidence:.2f} below threshold {settings.hitl_confidence_threshold}",
                context={"plan": state.plan.model_dump(), "original_request": state.original_request},
                proposed_action="Proceed with the generated execution plan",
                agent_reasoning=state.plan.reasoning,
            )
            state.status = TaskStatus.AWAITING_HUMAN
        else:
            state.status = TaskStatus.EXECUTING

        return state

    def _synthesize(self, state: AgentState) -> AgentState:
        self.log.info("synthesizing_output", task_id=state.task_id)

        specialist_outputs = "\n\n".join(
            f"[{sid}]: {output}" for sid, output in state.subtask_outputs.items()
        )

        messages = [
            SystemMessage(content=SYNTHESIS_SYSTEM_PROMPT),
            HumanMessage(
                content=(
                    f"Original request: {state.original_request}\n\n"
                    f"Specialist outputs:\n{specialist_outputs}\n\n"
                    "Synthesize a final answer."
                )
            ),
        ]

        response = self._invoke_llm(messages, state)
        state.final_output = response.content
        state.status = TaskStatus.COMPLETED
        self._emit_trace(state, "synthesis_complete", {"output_length": len(state.final_output)})
        return state
