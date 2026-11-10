"""Opt-in, bounded HTTP dependency for M6 delayed-downstream verification.

The only destination is the in-namespace M6 test service. This module never
accepts operator- or experiment-supplied arbitrary URLs. Test-only GETs are
safe to retry. No dependency is contacted unless the feature flag is enabled.
"""

import logging
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
            request = Request(url, method="GET", headers={"Accept": "application/json"})
            with urlopen(request, timeout=timeout_ms / 1000) as response:  # noqa: S310
                if response.status != 200:
                    raise RuntimeError("M6 downstream returned an unexpected status")
                if len(response.read(1025)) > 1024:
                    raise RuntimeError("M6 downstream payload exceeded bound")
                logger.info("M6 downstream dependency responded")
                return
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            if attempt + 1 >= attempts:
                raise RuntimeError("M6 downstream fixture unreachable or timed out") from exc
            time.sleep(0.1 * (attempt + 1))
