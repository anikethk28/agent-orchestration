"""Celery tasks for async agent execution."""
from __future__ import annotations

import structlog

from orchestration.graph.state import AgentState, TaskStatus
from orchestration.graph.workflow import compile_graph
from orchestration.hitl.escalation import apply_human_resolution
from orchestration.hitl.queue import enqueue_review, wait_for_resolution
from orchestration.memory.semantic import retrieve_relevant_memories, save_task_memory
from orchestration.memory.working import clear_working_memory, set_working_memory
from orchestration.observability.metrics import get_task_metrics, start_task_metrics
from orchestration.tools.setup import register_all_tools

from .celery_app import app

log = structlog.get_logger()


@app.task(bind=True, name="orchestration.workers.tasks.run_task", max_retries=0)
def run_task(self, task_id: str, user_id: str, request: str) -> dict:
    """Main orchestration task — runs the full agent workflow."""
    register_all_tools()
    metrics = start_task_metrics(task_id)

    # Retrieve relevant memories to inform planning
    try:
        memories = retrieve_relevant_memories(request, user_id=user_id)
    except Exception:
        memories = []

    state = AgentState(
        task_id=task_id,
        user_id=user_id,
        original_request=request,
        retrieved_memories=memories,
    )

    # Persist initial state to working memory
    set_working_memory(task_id, "state", state.model_dump())
    set_working_memory(task_id, "status", TaskStatus.PENDING.value)

    graph = compile_graph()

    try:
        # LangGraph execution — handles agent routing internally
        for event in graph.stream(state, stream_mode="values"):
            current_state = AgentState(**event) if isinstance(event, dict) else event

            # Persist current state
            set_working_memory(task_id, "state", current_state.model_dump())
            set_working_memory(task_id, "status", current_state.status.value)

            # Handle HITL escalation
            if current_state.status == TaskStatus.AWAITING_HUMAN and current_state.pending_review:
                review = current_state.pending_review
                enqueue_review(review)
                metrics.escalation_count += 1

                log.info("waiting_for_human_review", task_id=task_id, review_id=review.id)
                resolution = wait_for_resolution(review.id)

                if resolution is None:
                    current_state.status = TaskStatus.FAILED
                    current_state.error = "Human review timed out"
                    break

                import time
                review_start = time.time()
                current_state = apply_human_resolution(
                    current_state,
                    resolution=resolution.get("resolution", ""),
                    approved=resolution.get("approved", False),
                    notes=resolution.get("notes", ""),
                )
                metrics.human_review_time_seconds += time.time() - review_start

                if not current_state.human_approved:
                    break

                # Re-enter graph from current state
                for sub_event in graph.stream(current_state, stream_mode="values"):
                    current_state = AgentState(**sub_event) if isinstance(sub_event, dict) else sub_event
                    set_working_memory(task_id, "state", current_state.model_dump())
                    if current_state.status in (TaskStatus.COMPLETED, TaskStatus.FAILED):
                        break
                break

        # Save learnings to long-term memory
        if current_state.status == TaskStatus.COMPLETED:
            try:
                save_task_memory(current_state)
            except Exception as exc:
                log.warning("memory_save_failed", error=str(exc))

    except Exception as exc:
        log.error("task_execution_error", task_id=task_id, error=str(exc))
        current_state.status = TaskStatus.FAILED
        current_state.error = str(exc)
    finally:
        metrics.complete()
        clear_working_memory(task_id)

    return {
        "task_id": task_id,
        "status": current_state.status.value,
        "final_output": current_state.final_output,
        "error": current_state.error,
        "metrics": metrics.to_dict(),
        "trace_events": [e.model_dump() for e in current_state.trace_events],
    }
