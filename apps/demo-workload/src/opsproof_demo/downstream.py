"""Opt-in, bounded HTTP dependency for M6 delayed-downstream verification.

The only destination is the in-namespace M6 test service. This module never
accepts operator- or experiment-supplied arbitrary URLs. Test-only GETs are
safe to retry. No dependency is contacted unless the feature flag is enabled.
"""

import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from opentelemetry import propagate, trace
from opentelemetry.trace import SpanKind

logger = logging.getLogger(__name__)
ALLOWED_URL = "http://demo-downstream.opsproof-demo.svc.cluster.local:8080/work"


def probe(*, enabled: bool, url: str, timeout_ms: int, attempts: int) -> None:
    if not enabled:
        return
    if url != ALLOWED_URL:
        raise ValueError("M6 downstream target must be the fixed in-namespace fixture")
    if type(timeout_ms) is not int or not 100 <= timeout_ms <= 2000:
        raise ValueError("M6 timeout must be within 100..2000 ms")
    if type(attempts) is not int or not 1 <= attempts <= 2:
        raise ValueError("M6 attempts must be within 1..2")
    # A maximum of two bounded GETs; no business side effects in the fixture.
    for attempt in range(attempts):
        try:
            with trace.get_tracer(__name__).start_as_current_span(
                "opsproof.downstream",
                kind=SpanKind.CLIENT,
                attributes={
                    "http.request.method": "GET",
                    "server.address": "demo-downstream",
                    "opsproof.attempt": attempt + 1,
                    "opsproof.timeout_ms": timeout_ms,
                },
            ) as span:
                headers = {"Accept": "application/json"}
                propagate.inject(headers)
                request = Request(url, method="GET", headers=headers)
                started = time.monotonic()
                with urlopen(request, timeout=timeout_ms / 1000) as response:  # noqa: S310
                    if response.status != 200:
                        raise RuntimeError("M6 downstream returned an unexpected status")
                    if len(response.read(1025)) > 1024:
                        raise RuntimeError("M6 downstream payload exceeded bound")
                    span.set_attribute("http.response.status_code", response.status)
                    logger.info(
                        "M6 downstream responded attempt=%s elapsed_ms=%.2f",
                        attempt + 1,
                        (time.monotonic() - started) * 1000,
                    )
                    return
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            logger.warning(
                "M6 downstream failed attempt=%s timeout_ms=%s error=%s",
                attempt + 1,
                timeout_ms,
                type(exc).__name__,
            )
            if attempt + 1 >= attempts:
                raise RuntimeError("M6 downstream fixture unreachable or timed out") from exc
            time.sleep(0.1 * (attempt + 1))
