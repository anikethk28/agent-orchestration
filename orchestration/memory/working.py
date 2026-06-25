"""Short-term working memory backed by Redis — scoped to a single task execution."""
from __future__ import annotations

import json
from typing import Any

import redis
import structlog

from orchestration.config import get_settings

log = structlog.get_logger()

TTL_SECONDS = 3600  # Working memory expires after 1 hour


def _client() -> redis.Redis:
    settings = get_settings()
    return redis.from_url(settings.redis_url, decode_responses=True)


def _key(task_id: str, field: str) -> str:
    return f"wm:{task_id}:{field}"


def set_working_memory(task_id: str, field: str, value: Any) -> None:
    client = _client()
    key = _key(task_id, field)
    client.setex(key, TTL_SECONDS, json.dumps(value, default=str))


def get_working_memory(task_id: str, field: str) -> Any | None:
    client = _client()
    raw = client.get(_key(task_id, field))
    if raw is None:
        return None
    return json.loads(raw)


def update_working_memory(task_id: str, updates: dict[str, Any]) -> None:
    client = _client()
    pipe = client.pipeline()
    for field, value in updates.items():
        pipe.setex(_key(task_id, field), TTL_SECONDS, json.dumps(value))
    pipe.execute()


def get_all_working_memory(task_id: str) -> dict[str, Any]:
    client = _client()
    pattern = _key(task_id, "*")
    keys = client.keys(pattern)
    if not keys:
        return {}
    values = client.mget(*keys)
    prefix = f"wm:{task_id}:"
    return {
        key.replace(prefix, ""): json.loads(val)
        for key, val in zip(keys, values)
        if val is not None
    }


def clear_working_memory(task_id: str) -> None:
    client = _client()
    pattern = _key(task_id, "*")
    keys = client.keys(pattern)
    if keys:
        client.delete(*keys)
    log.info("working_memory_cleared", task_id=task_id)


def push_to_error_log(task_id: str, error: dict[str, Any]) -> None:
    client = _client()
    key = f"wm:{task_id}:errors"
    client.lpush(key, json.dumps(error))
    client.expire(key, TTL_SECONDS)


def get_error_log(task_id: str) -> list[dict[str, Any]]:
    client = _client()
    key = f"wm:{task_id}:errors"
    raw_list = client.lrange(key, 0, -1)
    return [json.loads(r) for r in raw_list]
