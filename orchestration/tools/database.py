"""Read-only database query tool backed by SQLAlchemy."""
from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from orchestration.config import get_settings

from .registry import ToolDefinition, get_registry

log = structlog.get_logger()

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(settings.database_url, pool_pre_ping=True)
    return _engine


def database_query(sql: str, params: dict[str, Any] | None = None) -> dict:
    """Execute a read-only SQL query and return rows as a list of dicts."""
    stripped = sql.strip().upper()
    if not stripped.startswith("SELECT"):
        raise ValueError("Only SELECT statements are permitted for the database_query tool.")

    try:
        with _get_engine().connect() as conn:
            result = conn.execute(text(sql), params or {})
            rows = [dict(row._mapping) for row in result]
            return {"success": True, "rows": rows, "count": len(rows)}
    except SQLAlchemyError as exc:
        log.error("db_query_error", error=str(exc))
        return {"success": False, "rows": [], "count": 0, "error": str(exc)}


def register_database(registry=None) -> None:
    if registry is None:
        registry = get_registry()
    registry.register(
        ToolDefinition(
            name="database_query",
            description="Execute a read-only SQL SELECT query against the application database.",
            fn=database_query,
            allowed_specialists=["analyst", "researcher"],
            input_schema={"sql": "str — SELECT statement only", "params": "dict (optional)"},
            output_schema={"success": "bool", "rows": "list[dict]", "count": "int"},
            rate_limit_rpm=30,
        )
    )
