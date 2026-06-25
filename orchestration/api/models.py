"""Pydantic request/response models for the API."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SubmitTaskRequest(BaseModel):
    request: str
    user_id: str = "default"


class SubmitTaskResponse(BaseModel):
    task_id: str
    celery_task_id: str
    status: str = "pending"
    message: str = "Task submitted for async execution"


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    final_output: str | None = None
    error: str | None = None
    metrics: dict[str, Any] | None = None
    trace_events: list[dict[str, Any]] = []
    pending_review: dict[str, Any] | None = None


class ReviewResolutionRequest(BaseModel):
    approved: bool
    resolution: str
    notes: str = ""


class ReviewResolutionResponse(BaseModel):
    review_id: str
    resolved: bool
    message: str


class MemoryStatsResponse(BaseModel):
    total_memories: int
    most_accessed: list[dict[str, Any]]


class ToolStatsResponse(BaseModel):
    stats: dict[str, Any]


class SystemHealthResponse(BaseModel):
    status: str
    redis: bool
    chroma: bool
    postgres: bool
    pending_reviews: int
    timestamp: datetime
