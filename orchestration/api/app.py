"""FastAPI application factory."""
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from orchestration.observability.tracing import setup_tracing
from orchestration.tools.setup import register_all_tools

from .routes import router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    register_all_tools()
    log.info("agent_orchestration_started")
    yield
    log.info("agent_orchestration_stopped")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agent Orchestration System",
        description="Multi-agent platform with tool use, persistent memory, and human-in-the-loop",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router, prefix="/api/v1")

    FastAPIInstrumentor.instrument_app(app)
    return app


application = create_app()
