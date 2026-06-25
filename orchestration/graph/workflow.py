"""LangGraph workflow — wires supervisor, specialists, and reviewer into a state machine."""
from __future__ import annotations

from typing import Any

import structlog
from langgraph.graph import END, StateGraph

from orchestration.agents.reviewer import ReviewerAgent
from orchestration.agents.specialists.analyst import AnalystAgent
from orchestration.agents.specialists.coder import CoderAgent
from orchestration.agents.specialists.researcher import ResearcherAgent
from orchestration.agents.specialists.writer import WriterAgent
from orchestration.agents.supervisor import SupervisorAgent
from orchestration.graph.state import AgentState, SubtaskStatus, TaskStatus

log = structlog.get_logger()

# ── Node functions ──────────────────────────────────────────────────────────


def supervisor_node(state: AgentState) -> dict[str, Any]:
    agent = SupervisorAgent()
    updated = agent.run(state)
    return updated.model_dump()


def researcher_node(state: AgentState) -> dict[str, Any]:
    agent = ResearcherAgent()
    updated = agent.run(state)
    return updated.model_dump()


def analyst_node(state: AgentState) -> dict[str, Any]:
    agent = AnalystAgent()
    updated = agent.run(state)
    return updated.model_dump()


def writer_node(state: AgentState) -> dict[str, Any]:
    agent = WriterAgent()
    updated = agent.run(state)
    return updated.model_dump()


def coder_node(state: AgentState) -> dict[str, Any]:
    agent = CoderAgent()
    updated = agent.run(state)
    return updated.model_dump()


def reviewer_node(state: AgentState) -> dict[str, Any]:
    agent = ReviewerAgent()
    updated = agent.run(state)
    return updated.model_dump()


def human_review_node(state: AgentState) -> dict[str, Any]:
    """Pause point — in production this is awaited by the HITL queue."""
    log.info("awaiting_human_review", task_id=state.task_id, review_id=state.pending_review.id if state.pending_review else None)
    # The FastAPI endpoint resolves this node by pushing a resolution back via the queue.
    # In graph traversal mode it passes through; async execution blocks here.
    return state.model_dump()


# ── Routing functions ───────────────────────────────────────────────────────


def route_after_supervisor(state: AgentState) -> str:
    if state.status == TaskStatus.FAILED:
        return "end"
    if state.status == TaskStatus.AWAITING_HUMAN:
        return "human_review"
    if state.status == TaskStatus.REVIEWING:
        return "supervisor"  # synthesis pass
    if state.status == TaskStatus.COMPLETED:
        return "end"
    return "dispatch_specialists"


def route_dispatch(state: AgentState) -> str:
    """Pick the first pending specialist or move to review."""
    if state.plan is None:
        return "reviewer"

    for subtask in state.plan.subtasks:
        if subtask.status == SubtaskStatus.PENDING:
            deps_met = True
            for dep_id in subtask.depends_on:
                dep = next((s for s in state.plan.subtasks if s.id == dep_id), None)
                if dep is None or dep.status != SubtaskStatus.COMPLETED:
                    deps_met = False
                    break
            if deps_met:
                return subtask.specialist.value

    # All runnable subtasks done — go to review
    return "reviewer"


def route_after_specialist(state: AgentState) -> str:
    if state.status == TaskStatus.AWAITING_HUMAN:
        return "human_review"
    if state.status == TaskStatus.FAILED:
        return "end"
    # Continue dispatching until all subtasks resolved
    return "dispatch_specialists"


def route_after_reviewer(state: AgentState) -> str:
    if state.status == TaskStatus.AWAITING_HUMAN:
        return "human_review"
    if state.status == TaskStatus.REVIEWING:
        return "supervisor"  # synthesis
    # Some subtasks rejected — redispatch
    return "dispatch_specialists"


def route_after_human(state: AgentState) -> str:
    if state.human_approved is False:
        return "end"
    if state.status == TaskStatus.PLANNING:
        return "supervisor"
    return "dispatch_specialists"


# ── Graph assembly ──────────────────────────────────────────────────────────


def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("supervisor", supervisor_node)
    g.add_node("dispatch_specialists", lambda s: s.model_dump())  # pure routing node
    g.add_node("researcher", researcher_node)
    g.add_node("analyst", analyst_node)
    g.add_node("writer", writer_node)
    g.add_node("coder", coder_node)
    g.add_node("reviewer", reviewer_node)
    g.add_node("human_review", human_review_node)

    g.set_entry_point("supervisor")

    g.add_conditional_edges("supervisor", route_after_supervisor, {
        "dispatch_specialists": "dispatch_specialists",
        "human_review": "human_review",
        "supervisor": "supervisor",
        "end": END,
    })

    g.add_conditional_edges("dispatch_specialists", route_dispatch, {
        "researcher": "researcher",
        "analyst": "analyst",
        "writer": "writer",
        "coder": "coder",
        "reviewer": "reviewer",
    })

    for specialist in ["researcher", "analyst", "writer", "coder"]:
        g.add_conditional_edges(specialist, route_after_specialist, {
            "dispatch_specialists": "dispatch_specialists",
            "human_review": "human_review",
            "end": END,
        })

    g.add_conditional_edges("reviewer", route_after_reviewer, {
        "dispatch_specialists": "dispatch_specialists",
        "supervisor": "supervisor",
        "human_review": "human_review",
    })

    g.add_conditional_edges("human_review", route_after_human, {
        "supervisor": "supervisor",
        "dispatch_specialists": "dispatch_specialists",
        "end": END,
    })

    return g


def compile_graph():
    return build_graph().compile()
