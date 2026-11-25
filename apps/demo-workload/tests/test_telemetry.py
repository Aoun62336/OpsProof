"""Exercise actual propagation, legacy messages and bounded log correlation."""

import logging

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from opsproof_demo import telemetry


def test_context_survives_message_and_is_cleared(monkeypatch):
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry.trace, "get_tracer", lambda *_: provider.get_tracer("test"))
    with provider.get_tracer("test").start_as_current_span("admission") as parent:
        carrier = telemetry.capture_context()
        parent_context = parent.get_span_context()
    with telemetry.message_span("process", carrier, job_id="owned-job") as consumer:
        assert consumer.get_span_context().trace_id == parent_context.trace_id
        record = logging.LogRecord("test", logging.INFO, "", 1, "completed", (), None)
        telemetry.CorrelationFilter().filter(record)
        assert record.job_id == "owned-job"
        assert record.trace_id == format(parent_context.trace_id, "032x")
        assert consumer.parent.span_id == parent_context.span_id
    assert telemetry.CORRELATION.get() is None
    assert len(exporter.get_finished_spans()) == 2
    provider.shutdown()


def test_context_is_allowlisted_and_invalid_messages_still_run(monkeypatch):
    provider = TracerProvider()
    monkeypatch.setattr(telemetry.trace, "get_tracer", lambda *_: provider.get_tracer("test"))
    for invalid in (None, {}, {"traceparent": "invalid"}, {"traceparent": "x" * 1025}):
        assert telemetry.bounded_context(invalid) == {}
        with telemetry.message_span("legacy", invalid):
            assert trace.get_current_span().get_span_context().is_valid
    with provider.get_tracer("test").start_as_current_span("parent"):
        carrier = telemetry.capture_context()
        carrier.update(baggage="secret", authorization="secret")
        assert set(telemetry.bounded_context(carrier)) <= {"traceparent", "tracestate"}
    assert telemetry.CORRELATION.get() is None
    provider.shutdown()


def test_exception_keeps_failure_visible_and_clears_log_context(monkeypatch):
    import pytest

    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(telemetry.trace, "get_tracer", lambda *_: provider.get_tracer("test"))
    with pytest.raises(RuntimeError):
        with telemetry.message_span("attempt", {}, run_id="run"):
            raise RuntimeError("bounded test failure")
    assert telemetry.CORRELATION.get() is None
    assert exporter.get_finished_spans()[0].status.status_code == trace.StatusCode.ERROR
    provider.shutdown()
