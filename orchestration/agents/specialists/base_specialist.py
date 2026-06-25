"""Shared logic for all specialist agents."""
from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from orchestration.graph.state import (
    AgentState,
    EscalationLevel,
    HumanReviewRequest,
    SpecialistType,
    Subtask,
    SubtaskStatus,
    TaskStatus,
)
from orchestration.tools.registry import get_registry

from ..base import BaseAgent

SPECIALIST_SYSTEM_TEMPLATE = """\
You are a {role} specialist agent in a multi-agent system.
{domain_description}

You have access to the following tools: {tool_list}

To use a tool, output a JSON block exactly like this:
<tool_call>
{{"tool": "<tool_name>", "args": {{...}}}}
</tool_call>

After receiving tool results, continue reasoning. When you have enough information to complete your subtask, output your final answer prefixed with:
FINAL ANSWER:
<your complete answer here>

Current subtask: {subtask_description}
Expected output format: {expected_output_format}
"""


class BaseSpecialist(BaseAgent):
    specialist_type: SpecialistType
    domain_description: str = ""

    def run(self, state: AgentState) -> AgentState:
        if state.plan is None:
            state.error = "No execution plan found"
            state.status = TaskStatus.FAILED
            return state

        subtask = self._get_my_subtask(state)
        if subtask is None:
            return state

        subtask.status = SubtaskStatus.IN_PROGRESS
        self.log.info("specialist_start", specialist=self.specialist_type, subtask_id=subtask.id)

        context = self._build_context(subtask, state)
        result = self._agentic_loop(subtask, context, state)

        if result is not None:
            subtask.output = result
            subtask.status = SubtaskStatus.COMPLETED
            state.subtask_outputs[subtask.id] = result
            self._emit_trace(state, "subtask_completed", {"subtask_id": subtask.id, "output_length": len(result)})
        else:
            subtask.retry_count += 1
            if subtask.retry_count >= 2:
                subtask.status = SubtaskStatus.FAILED
                state.pending_review = HumanReviewRequest(
                    task_id=state.task_id,
                    level=EscalationLevel.APPROVE_ACTION,
                    trigger_reason=f"Specialist '{self.specialist_type}' failed twice on subtask",
                    context={"subtask": subtask.model_dump(), "task": state.original_request},
                    proposed_action="Retry with modified approach or skip this subtask",
                    agent_reasoning=f"Failed after {subtask.retry_count} attempts",
                )
                state.status = TaskStatus.AWAITING_HUMAN
            else:
                subtask.status = SubtaskStatus.PENDING

        return state

    def _get_my_subtask(self, state: AgentState) -> Subtask | None:
        if state.plan is None:
            return None
        for st in state.plan.subtasks:
            if st.specialist == self.specialist_type and st.status == SubtaskStatus.PENDING:
                if self._dependencies_met(st, state):
                    return st
        return None

    def _dependencies_met(self, subtask: Subtask, state: AgentState) -> bool:
        if not subtask.depends_on:
            return True
        plan = state.plan
        if plan is None:
            return True
        for dep_id in subtask.depends_on:
            dep = next((s for s in plan.subtasks if s.id == dep_id), None)
            if dep is None or dep.status != SubtaskStatus.COMPLETED:
                return False
        return True

    def _build_context(self, subtask: Subtask, state: AgentState) -> str:
        parts = [f"Original task: {state.original_request}"]
        for dep_id in subtask.depends_on:
            dep_output = state.subtask_outputs.get(dep_id)
            if dep_output:
                parts.append(f"Input from prior subtask ({dep_id}):\n{dep_output}")
        return "\n\n".join(parts)

    def _agentic_loop(self, subtask: Subtask, context: str, state: AgentState, max_turns: int = 5) -> str | None:
        registry = get_registry()
        available_tools = registry.list_for_specialist(self.specialist_type.value)
        tool_list = ", ".join(t.name for t in available_tools) if available_tools else "none"

        system = SPECIALIST_SYSTEM_TEMPLATE.format(
            role=self.specialist_type.value,
            domain_description=self.domain_description,
            tool_list=tool_list,
            subtask_description=subtask.description,
            expected_output_format=subtask.expected_output_format,
        )
        messages = [SystemMessage(content=system), HumanMessage(content=context)]

        for turn in range(max_turns):
            response = self._invoke_llm(messages, state)
            content = response.content

            if "FINAL ANSWER:" in content:
                return content.split("FINAL ANSWER:", 1)[1].strip()

            if "<tool_call>" in content:
                tool_result = self._execute_tool_call(content, state)
                messages.append(response)
                messages.append(HumanMessage(content=f"Tool result:\n{tool_result}"))
            else:
                messages.append(response)

        self.log.warning("agentic_loop_exhausted", subtask_id=subtask.id, turns=max_turns)
        return None

    @staticmethod
    def _fix_json_strings(raw: str) -> str:
        """Escape literal newlines/tabs inside JSON string values — common LLM mistake."""
        result = []
        in_string = False
        i = 0
        while i < len(raw):
            c = raw[i]
            if c == "\\" and in_string:
                result.append(c)
                i += 1
                if i < len(raw):
                    result.append(raw[i])
                i += 1
                continue
            if c == '"':
                in_string = not in_string
                result.append(c)
            elif in_string and c == "\n":
                result.append("\\n")
            elif in_string and c == "\t":
                result.append("\\t")
            elif in_string and c == "\r":
                result.append("\\r")
            else:
                result.append(c)
            i += 1
        return "".join(result)

    def _execute_tool_call(self, content: str, state: AgentState) -> str:
        registry = get_registry()
        try:
            raw = content.split("<tool_call>")[1].split("</tool_call>")[0].strip()
            try:
                call, _ = json.JSONDecoder().raw_decode(raw)
            except json.JSONDecodeError:
                call, _ = json.JSONDecoder().raw_decode(self._fix_json_strings(raw))
            tool_name = call["tool"]
            args = call.get("args", {})
            result = registry.invoke(tool_name, agent=self.name, **args)
            self._emit_trace(state, "tool_call", {"tool": tool_name, "args": args, "result_preview": str(result)[:300]})
            return json.dumps(result) if isinstance(result, (dict, list)) else str(result)
        except Exception as exc:
            self.log.error("tool_call_failed", error=str(exc))
            return f"Error: {exc}"
