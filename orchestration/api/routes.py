"""FastAPI route definitions."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import structlog
from celery.result import AsyncResult
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from orchestration.hitl.queue import (
    get_review,
    get_review_stats,
    list_pending_reviews,
    resolve_review,
)
from orchestration.memory.semantic import delete_user_memories, get_memory_stats
from orchestration.memory.working import get_all_working_memory, get_working_memory
from orchestration.observability.metrics import aggregate_metrics, get_task_metrics
from orchestration.observability.tracing import get_finished_spans
from orchestration.tools.registry import get_registry
from orchestration.workers.celery_app import app as celery_app
from orchestration.workers.tasks import run_task

from .models import (
    MemoryStatsResponse,
    ReviewResolutionRequest,
    ReviewResolutionResponse,
    SubmitTaskRequest,
    SubmitTaskResponse,
    SystemHealthResponse,
    TaskStatusResponse,
    ToolStatsResponse,
)

log = structlog.get_logger()
router = APIRouter()


# ── Tasks ───────────────────────────────────────────────────────────────────


@router.post("/tasks", response_model=SubmitTaskResponse)
async def submit_task(body: SubmitTaskRequest) -> SubmitTaskResponse:
    task_id = str(uuid.uuid4())
    result = run_task.apply_async(
        kwargs={"task_id": task_id, "user_id": body.user_id, "request": body.request},
        task_id=task_id,
    )
    log.info("task_submitted", task_id=task_id, user_id=body.user_id)
    return SubmitTaskResponse(task_id=task_id, celery_task_id=result.id)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    result = AsyncResult(task_id, app=celery_app)

    # First check working memory for live state
    wm = get_all_working_memory(task_id)
    pending_review_raw = get_working_memory(task_id, "pending_review")

    if result.ready():
        if result.successful():
            data = result.result
            return TaskStatusResponse(**data)
        else:
            return TaskStatusResponse(task_id=task_id, status="failed", error=str(result.result))

    status = wm.get("status", "pending")
    return TaskStatusResponse(
        task_id=task_id,
        status=status,
        pending_review=pending_review_raw,
    )


@router.get("/tasks/{task_id}/trace")
async def get_task_trace(task_id: str) -> dict[str, Any]:
    wm = get_all_working_memory(task_id)
    state = wm.get("state", {})
    return {
        "task_id": task_id,
        "trace_events": state.get("trace_events", []),
        "otel_spans": get_finished_spans(),
    }


# ── Human-in-the-loop ───────────────────────────────────────────────────────


@router.get("/reviews")
async def list_reviews() -> dict[str, Any]:
    reviews = list_pending_reviews()
    stats = get_review_stats()
    return {
        "pending": [r.model_dump() for r in reviews],
        "stats": stats,
    }


@router.get("/reviews/{review_id}")
async def get_review_detail(review_id: str) -> dict[str, Any]:
    review = get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review.model_dump()


@router.post("/reviews/{review_id}/resolve", response_model=ReviewResolutionResponse)
async def resolve_review_endpoint(review_id: str, body: ReviewResolutionRequest) -> ReviewResolutionResponse:
    ok = resolve_review(
        review_id=review_id,
        approved=body.approved,
        resolution=body.resolution,
        notes=body.notes,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Review not found or already resolved")
    return ReviewResolutionResponse(
        review_id=review_id,
        resolved=True,
        message="Review resolved; task will resume" if body.approved else "Task cancelled by reviewer",
    )


# ── Memory ──────────────────────────────────────────────────────────────────


@router.get("/memory/stats", response_model=MemoryStatsResponse)
async def memory_stats(user_id: str = "default") -> MemoryStatsResponse:
    stats = get_memory_stats(user_id=user_id)
    return MemoryStatsResponse(**stats)


@router.delete("/memory/{user_id}")
async def delete_memory(user_id: str) -> dict[str, Any]:
    count = delete_user_memories(user_id)
    return {"deleted_count": count, "user_id": user_id}


# ── Observability ────────────────────────────────────────────────────────────


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    return aggregate_metrics()


@router.get("/tools/stats", response_model=ToolStatsResponse)
async def tool_stats() -> ToolStatsResponse:
    return ToolStatsResponse(stats=get_registry().get_stats())


# ── System ──────────────────────────────────────────────────────────────────


@router.get("/health", response_model=SystemHealthResponse)
async def health_check() -> SystemHealthResponse:
    redis_ok = chroma_ok = postgres_ok = False

    try:
        import redis as redis_lib
        from orchestration.config import get_settings
        r = redis_lib.from_url(get_settings().redis_url)
        r.ping()
        redis_ok = True
    except Exception:
        pass

    try:
        import chromadb
        from orchestration.config import get_settings
        s = get_settings()
        chromadb.HttpClient(host=s.chroma_host, port=s.chroma_port).heartbeat()
        chroma_ok = True
    except Exception:
        pass

    try:
        from sqlalchemy import text, create_engine
        from orchestration.config import get_settings
        engine = create_engine(get_settings().database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        postgres_ok = True
    except Exception:
        pass

    stats = get_review_stats()
    return SystemHealthResponse(
        status="healthy" if all([redis_ok, chroma_ok]) else "degraded",
        redis=redis_ok,
        chroma=chroma_ok,
        postgres=postgres_ok,
        pending_reviews=stats.get("pending_reviews", 0),
        timestamp=datetime.utcnow(),
    )
