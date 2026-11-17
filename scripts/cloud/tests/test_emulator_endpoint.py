"""The emulator runner cannot silently fall through to real AWS endpoints."""

import pytest

from scripts.cloud.validate_emulator import require_local_endpoint


@pytest.mark.parametrize(
    "url",
    [
        "https://secretsmanager.ap-south-1.amazonaws.com",
        "http://127.0.0.1:9297",
        "https://localhost:9297",
        "https://127.0.0.1:443",
        "https://127.0.0.1.evil.example:9297",
        "https://credential@127.0.0.1:9297",
    ],
)
def test_external_or_ambiguous_endpoint_is_rejected(url):
    with pytest.raises(ValueError):
        require_local_endpoint(url)


def test_exact_owned_loopback_endpoint_is_accepted():
    require_local_endpoint("https://127.0.0.1:9297/__admin/health")
