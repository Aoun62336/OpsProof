"""Provider contract checks without contacting a paid API."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from opsproof_control import model_provider as provider
from opsproof_control.benchmark import CASES, make_snapshot
from opsproof_control.diagnosis import deterministic


def test_disabled_provider_never_calls_network(monkeypatch):
    monkeypatch.setattr(provider, "settings", lambda: SimpleNamespace(ai_enabled=False))
    client = MagicMock()
    monkeypatch.setattr(provider.httpx, "Client", client)
    with pytest.raises(ValueError):
        provider.compare(make_snapshot(CASES[0]))
    client.assert_not_called()


@pytest.mark.parametrize("name", ["openai", "gemini"])
@pytest.mark.parametrize("malicious", [False, True])
def test_structured_provider_output(monkeypatch, name, malicious):
    monkeypatch.setattr(
        provider,
        "settings",
        lambda: SimpleNamespace(
            ai_enabled=True, ai_api_key="test-key", ai_provider=name, ai_model="test-model"
        ),
    )
    snapshot = make_snapshot(CASES[0])
    diagnosis = deterministic(snapshot).model_dump()
    if malicious:
        diagnosis["shell_command"] = "unexpected"
    output = json.dumps(diagnosis)
    data = (
        {
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "text": output}]}],
            "usage": {"input_tokens": 20, "output_tokens": 30},
        }
        if name == "openai"
        else {
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": output}]}}],
            "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 30},
        }
    )
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.post.return_value.json.return_value = data
    monkeypatch.setattr(provider.httpx, "Client", factory)
    if malicious:
        with pytest.raises(ValueError):
            provider.compare(snapshot)
    else:
        result = provider.compare(snapshot)
        assert result["usage"] == {"input_tokens": 20, "output_tokens": 30}
        assert result["diagnosis"] == diagnosis
    body = json.dumps(client.post.call_args.kwargs["json"])
    assert snapshot.incident_fingerprint not in body
    assert str(snapshot.job_ids[0]) not in body
    assert "tools" not in client.post.call_args.kwargs["json"]
