import httpx2 as httpx
import pytest

from opsproof_control import kubernetes_client


def test_missing_credential_fails_before_network(monkeypatch, tmp_path):
    monkeypatch.setattr(kubernetes_client, "TOKEN", tmp_path / "missing-token")
    with pytest.raises(FileNotFoundError):
        kubernetes_client.request()


@pytest.mark.parametrize("method", ["DELETE", "POST", "PUT", "CONNECT"])
def test_unsupported_operations_never_reach_network(method):
    with pytest.raises(ValueError, match="Unsupported"):
        kubernetes_client.request(method)


def test_scaler_inspection_cannot_be_a_mutation():
    with pytest.raises(ValueError, match="read-only"):
        kubernetes_client.request("PATCH", [], check_scaler=True)


@pytest.mark.parametrize("method,patch", [("GET", None), ("PATCH", [])])
def test_transport_failure_is_not_an_acknowledgment(monkeypatch, tmp_path, method, patch):
    token = tmp_path / "token"
    token.write_text("test-only")
    monkeypatch.setattr(kubernetes_client, "TOKEN", token)
    monkeypatch.setattr(kubernetes_client.ssl, "create_default_context", lambda **_: object())

    class Unavailable:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def request(self, *args, **kwargs):
            raise httpx.ConnectError("Simulated transient Kubernetes failure")

    monkeypatch.setattr(kubernetes_client.httpx, "Client", Unavailable)
    with pytest.raises(httpx.ConnectError):
        kubernetes_client.request(method, patch)
