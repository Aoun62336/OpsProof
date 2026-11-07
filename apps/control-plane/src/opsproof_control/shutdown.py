"""Cooperative process shutdown at durable work boundaries."""

import logging
import signal
from contextlib import contextmanager
from threading import Event

logger = logging.getLogger(__name__)
stopping = Event()


class ShutdownRequested(BaseException):
    """Leave retryable work pending, without reporting a business failure."""


def checkpoint() -> None:
    if stopping.is_set():
        raise ShutdownRequested


@contextmanager
def lifecycle():
    """Install handlers only on worker entry; keep API signal handling unchanged."""
    stopping.clear()

    def request_stop(signum, frame):
        stopping.set()

    previous = {s: signal.signal(s, request_stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        yield
    except ShutdownRequested:
        pass
    finally:
        stopping.set()
        for signum, handler in previous.items():
            signal.signal(signum, handler)
        logger.info("Worker shutdown complete")
