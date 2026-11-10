"""Bounded fail-closed M6 test-only downstream contract tests."""
from unittest.mock import patch

import pytest

from opsproof_demo.downstream import ALLOWED_URL, probe


class Response:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_args): return False
    def read(self, _limit): return b'{"status":"ok"}'


def test_off_does_not_contact_network():
    with patch("opsproof_demo.downstream.urlopen") as call:
        probe(enabled=False, url="http://untrusted", timeout_ms=1, attempts=100)
        call.assert_not_called()


def test_only_fixed_dependency_is_allowed():
    with pytest.raises(ValueError):
        probe(enabled=True, url="http://127.0.0.1/admin", timeout_ms=400, attempts=1)


def test_bounded_timeout_and_attempts():
    for timeout, attempts in ((0, 1), (2001, 1), (400, 0), (400, 3)):
        with pytest.raises(ValueError):
            probe(enabled=True, url=ALLOWED_URL, timeout_ms=timeout, attempts=attempts)


def test_real_http_call_is_required():
    with patch("opsproof_demo.downstream.urlopen", return_value=Response()) as call:
        probe(enabled=True, url=ALLOWED_URL, timeout_ms=400, attempts=1)
        call.assert_called_once()
