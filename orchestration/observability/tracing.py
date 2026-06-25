"""OpenTelemetry tracing setup and span helpers."""
from __future__ import annotations

import functools
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from orchestration.config import get_settings

_in_memory_exporter: InMemorySpanExporter | None = None
_tracer: trace.Tracer | None = None


def setup_tracing(use_console: bool = False) -> None:
    global _in_memory_exporter, _tracer
    settings = get_settings()

    resource = Resource.create({"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    _in_memory_exporter = InMemorySpanExporter()
    provider.add_span_processor(BatchSpanProcessor(_in_memory_exporter))

    if use_console or settings.debug:
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    try:
        otlp = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp))
    except Exception:
        pass  # OTLP collector optional

    trace.set_tracer_provider(provider)
    _tracer = trace.get_tracer(settings.otel_service_name)


def get_tracer() -> trace.Tracer:
    global _tracer
    if _tracer is None:
        setup_tracing()
    return _tracer


@contextmanager
def agent_span(agent_name: str, task_id: str, **attributes: Any):
    tracer = get_tracer()
    with tracer.start_as_current_span(f"{agent_name}.run") as span:
        span.set_attribute("agent.name", agent_name)
        span.set_attribute("task.id", task_id)
        for k, v in attributes.items():
            span.set_attribute(k, str(v))
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            raise


@contextmanager
def tool_span(tool_name: str, agent_name: str, **inputs: Any):
    tracer = get_tracer()
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        span.set_attribute("tool.name", tool_name)
        span.set_attribute("agent.name", agent_name)
        for k, v in inputs.items():
            span.set_attribute(f"tool.input.{k}", str(v)[:256])
        yield span


def get_finished_spans() -> list[dict[str, Any]]:
    if _in_memory_exporter is None:
        return []
    spans = []
    for span in _in_memory_exporter.get_finished_spans():
        spans.append({
            "name": span.name,
            "trace_id": format(span.context.trace_id, "032x"),
            "span_id": format(span.context.span_id, "016x"),
            "start_time": span.start_time,
            "end_time": span.end_time,
            "duration_ms": (span.end_time - span.start_time) / 1_000_000 if span.end_time else None,
            "attributes": dict(span.attributes or {}),
            "status": span.status.status_code.name,
            "events": [{"name": e.name, "attributes": dict(e.attributes or {})} for e in span.events],
        })
    return spans
