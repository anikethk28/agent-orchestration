"""Celery application and async task definitions."""
from __future__ import annotations

from celery import Celery

from orchestration.config import get_settings

settings = get_settings()

app = Celery(
    "agent_orchestration",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["orchestration.workers.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "orchestration.workers.tasks.run_task": {"queue": "orchestration"},
        "orchestration.workers.tasks.run_specialist": {"queue": "specialists"},
    },
)
