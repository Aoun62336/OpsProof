"""Bounded W3C message context and correlated logging for this application."""

import logging
from contextlib import contextmanager
from contextvars import ContextVar

from opentelemetry import trace
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

PROPAGATOR = TraceContextTextMapPropagator()
CORRELATION = ContextVar("operation_correlation", default=None)


def bounded_context(value):
    if not isinstance(value, dict):
        return {}
    carrier = {
        key: value[key]
        for key, limit in (("traceparent", 55), ("tracestate", 512))
        if isinstance(value.get(key), str) and len(value[key]) <= limit
    }
    context = PROPAGATOR.extract(carrier)
    if not trace.get_current_span(context).get_span_context().is_valid:
        return {}
    clean = {}
    PROPAGATOR.inject(clean, context=context)
    return clean


def capture_context():
    carrier = {}
    PROPAGATOR.inject(carrier)
    return bounded_context(carrier)


@contextmanager
def message_span(name, carrier, *, kind=trace.SpanKind.CONSUMER, **identifiers):
    token = CORRELATION.set(
        {k: str(v) for k, v in identifiers.items() if k in {"job_id", "run_id"}}
    )
    try:
        with trace.get_tracer(__name__).start_as_current_span(
            name,
            context=PROPAGATOR.extract(bounded_context(carrier)),
            kind=kind,
            attributes={"opsproof." + k: v for k, v in (CORRELATION.get() or {}).items()},
        ) as span:
            yield span
    finally:
        CORRELATION.reset(token)


class CorrelationFilter(logging.Filter):
    def filter(self, record):
        context = trace.get_current_span().get_span_context()
        record.trace_id = format(context.trace_id, "032x") if context.is_valid else ""
        record.span_id = format(context.span_id, "016x") if context.is_valid else ""
        for key in ("job_id", "run_id"):
            setattr(record, key, (CORRELATION.get() or {}).get(key, ""))
        return True


def configure_logging():
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.addFilter(CorrelationFilter())
        if isinstance(handler, logging.StreamHandler):
            handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(levelname)s %(name)s trace_id=%(trace_id)s "
                    "span_id=%(span_id)s job_id=%(job_id)s run_id=%(run_id)s %(message)s"
                )
            )
