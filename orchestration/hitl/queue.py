"""Human review queue — persists pending reviews in Redis and PostgreSQL."""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import redis
import structlog
from sqlalchemy import Column, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from orchestration.config import get_settings
from orchestration.graph.state import HumanReviewRequest

log = structlog.get_logger()

REVIEW_QUEUE_KEY = "hitl:review_queue"
REVIEW_HASH_KEY = "hitl:reviews"


# ── Redis-backed queue ──────────────────────────────────────────────────────


def _redis() -> redis.Redis:
    return redis.from_url(get_settings().redis_url, decode_responses=True)


def enqueue_review(review: HumanReviewRequest) -> None:
    r = _redis()
    payload = review.model_dump_json()
    r.hset(REVIEW_HASH_KEY, review.id, payload)
    r.lpush(REVIEW_QUEUE_KEY, review.id)
    log.info("review_enqueued", review_id=review.id, level=review.level, task_id=review.task_id)


def dequeue_next_review() -> HumanReviewRequest | None:
    r = _redis()
    review_id = r.rpop(REVIEW_QUEUE_KEY)
    if not review_id:
        return None
    payload = r.hget(REVIEW_HASH_KEY, review_id)
    if not payload:
        return None
    return HumanReviewRequest.model_validate_json(payload)


def get_review(review_id: str) -> HumanReviewRequest | None:
    r = _redis()
    payload = r.hget(REVIEW_HASH_KEY, review_id)
    if not payload:
        return None
    return HumanReviewRequest.model_validate_json(payload)


def list_pending_reviews() -> list[HumanReviewRequest]:
    r = _redis()
    pending_ids = r.lrange(REVIEW_QUEUE_KEY, 0, -1)
    reviews = []
    for rid in pending_ids:
        payload = r.hget(REVIEW_HASH_KEY, rid)
        if payload:
            reviews.append(HumanReviewRequest.model_validate_json(payload))
    return reviews


def resolve_review(review_id: str, approved: bool, resolution: str, notes: str = "") -> bool:
    r = _redis()
    payload = r.hget(REVIEW_HASH_KEY, review_id)
    if not payload:
        return False

    review = HumanReviewRequest.model_validate_json(payload)
    review.resolved_at = datetime.utcnow()
    review.resolution = resolution
    review.reviewer_notes = notes

    r.hset(REVIEW_HASH_KEY, review_id, review.model_dump_json())
    # Remove from pending queue
    r.lrem(REVIEW_QUEUE_KEY, 0, review_id)
    # Publish resolution event so waiting workers can resume
    r.publish(f"hitl:resolution:{review_id}", json.dumps({"approved": approved, "resolution": resolution, "notes": notes}))
    log.info("review_resolved", review_id=review_id, approved=approved)
    return True


def wait_for_resolution(review_id: str, timeout_seconds: int | None = None) -> dict[str, Any] | None:
    """Block until a resolution is published for this review (used by Celery workers)."""
    r = _redis()
    settings = get_settings()
    timeout = timeout_seconds or settings.hitl_review_timeout_seconds
    pubsub = r.pubsub()
    pubsub.subscribe(f"hitl:resolution:{review_id}")
    for message in pubsub.listen():
        if message["type"] == "message":
            pubsub.unsubscribe()
            return json.loads(message["data"])
    return None


def get_review_stats() -> dict[str, Any]:
    r = _redis()
    pending = r.llen(REVIEW_QUEUE_KEY)
    total = r.hlen(REVIEW_HASH_KEY)
    return {"pending_reviews": pending, "total_reviews": total}
