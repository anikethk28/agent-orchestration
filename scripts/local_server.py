#!/usr/bin/env python3
"""
Local development server — runs FastAPI + agent graph without Docker.

Replaces:
  - Redis  → fakeredis (in-memory, same process)
  - Celery → background threads

Usage:
    PYTHONPATH=. python scripts/local_server.py
"""
from __future__ import annotations

import sys
import threading
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()

# ── 1. Patch Redis with fakeredis before any other import touches it ────────
import fakeredis

_fake_server = fakeredis.FakeServer()


def _fake_redis_from_url(url, **kwargs):
    return fakeredis.FakeRedis(server=_fake_server, decode_responses=kwargs.get("decode_responses", False))


import redis as _redis_mod
_redis_mod.from_url = _fake_redis_from_url
_redis_mod.Redis.from_url = staticmethod(_fake_redis_from_url)

# ── 2. In-memory store for task results (replaces Celery result backend) ───
_task_results: dict[str, dict] = {}


class _FakeAsyncResult:
    def __init__(self, task_id, app=None):
        self.id = task_id

    def ready(self) -> bool:
        return self.id in _task_results

    def successful(self) -> bool:
        r = _task_results.get(self.id, {})
        return bool(r) and r.get("status") != "failed"

    @property
    def result(self):
        return _task_results.get(self.id, {})


# Patch AsyncResult in the routes module before it's used
import orchestration.api.routes as _routes_mod
_routes_mod.AsyncResult = _FakeAsyncResult  # type: ignore[attr-defined]

# ── 3. Run Celery tasks in background threads ───────────────────────────────
from orchestration.workers import tasks as _tasks_mod


def _thread_apply_async(kwargs: dict, task_id: str | None = None, **_):
    tid = task_id or str(uuid.uuid4())

    class _Handle:
        id = tid

    def _run():
        try:
            # run_task is bind=True — self is already bound on .run, so skip it
            result = _tasks_mod.run_task.run(**kwargs)
            _task_results[tid] = result
        except Exception as exc:
            _task_results[tid] = {
                "task_id": tid,
                "status": "failed",
                "error": str(exc),
                "final_output": None,
            }

    threading.Thread(target=_run, daemon=True, name=f"task-{tid[:8]}").start()
    return _Handle()


_tasks_mod.run_task.apply_async = _thread_apply_async  # type: ignore[attr-defined]

# ── 4. Silence OTEL console/OTLP output (no collector in local dev) ────────
import orchestration.observability.tracing as _tracing_mod
from opentelemetry import trace as _otel_trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource


def _quiet_setup_tracing(use_console: bool = False) -> None:
    resource = Resource.create({"service.name": "agent-orchestration-local"})
    provider = TracerProvider(resource=resource)
    _tracing_mod._in_memory_exporter = InMemorySpanExporter()
    provider.add_span_processor(BatchSpanProcessor(_tracing_mod._in_memory_exporter))
    _otel_trace.set_tracer_provider(provider)
    _tracing_mod._tracer = _otel_trace.get_tracer("agent-orchestration-local")


_tracing_mod.setup_tracing = _quiet_setup_tracing

# ── 5. Start uvicorn ────────────────────────────────────────────────────────
import uvicorn
from orchestration.api.app import create_app

if __name__ == "__main__":
    print("\n  Local API server → http://localhost:8000")
    print("  Streamlit UI    → http://localhost:8501\n")
    uvicorn.run(create_app(), host="0.0.0.0", port=8000, log_level="warning")
