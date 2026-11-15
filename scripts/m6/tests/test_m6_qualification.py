import json
from pathlib import Path

import pytest

from scripts.m6 import qualify
from scripts.m6.qualify import benchmark

DATASET = Path(__file__).parents[3] / "benchmarks/ai/qualification_v1.json"


def test_frozen_synthetic_labels_do_not_require_network():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    report = benchmark(data)
    assert report["case_count"] == 20
    assert report["hypothesis_correct"] == 20
    assert report["abstention_correct"] == 20
    assert report["invalid_or_error"] == 0
    assert all(row["prediction"]["action"] == "none" for row in report["cases"])


def test_corrupt_dataset_fails_closed():
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    data["cases"].pop()
    with pytest.raises(ValueError):
        benchmark(data)


@pytest.mark.parametrize("confirmed", [False, True])
def test_free_tier_cli_requires_confirmation_and_preserves_request_bound(
    monkeypatch, tmp_path, confirmed
):
    import sys

    calls = []

    def fake_benchmark(dataset, provider, max_cases, api_key):
        calls.append((provider, max_cases, api_key))
        return {
            "provider": provider,
            "case_count": max_cases,
            "hypothesis_correct": max_cases,
            "abstention_correct": max_cases,
            "invalid_or_error": 0,
            "cases": [],
        }

    arguments = [
        "qualify",
        "--provider",
        "groq",
        "--free-tier-only",
        "--authorization",
        "I_APPROVE_FREE_TIER_AI_CALLS",
        "--max-cases",
        "8",
        "--dataset",
        str(DATASET),
        "--output",
        str(tmp_path / "result.json"),
    ]
    if confirmed:
        arguments.append("--free-tier-confirmed")
    monkeypatch.setattr(sys, "argv", arguments)
    monkeypatch.setenv("GROQ_API_KEY", "local-test-placeholder")
    monkeypatch.setattr(qualify, "benchmark", fake_benchmark)
    if confirmed:
        qualify.main()
        assert calls == [("groq", 8, "local-test-placeholder")]
        result = json.loads((tmp_path / "result.json").read_text())
        assert result["billing_mode"] == "owner_confirmed_free_tier"
    else:
        with pytest.raises(SystemExit, match="2"):
            qualify.main()
        assert calls == []


def test_provider_error_retains_status_without_error_body_or_retry(monkeypatch):
    import httpx2 as httpx

    requests = []

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False
            assert kwargs["trust_env"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, **kwargs):
            requests.append(kwargs["json"])
            return httpx.Response(
                429,
                request=httpx.Request("POST", endpoint),
                json={"error": "private-provider-error"},
            )

    monkeypatch.setattr(httpx, "Client", Client)
    receipt = {}
    with pytest.raises(httpx.HTTPStatusError):
        qualify.provider_request("groq", {"metrics_fresh": False}, "test-key", receipt=receipt)
    assert len(requests) == 1
    assert requests[0]["max_completion_tokens"] == 1024
    assert receipt["http_status"] == 429
    assert "raw_response" not in receipt
    assert "private-provider-error" not in json.dumps(receipt)


def test_current_gemini_comparator_uses_bounded_structured_request(monkeypatch):
    import httpx2 as httpx

    requests = []
    prediction = {
        "hypothesis": "unknown",
        "abstained": True,
        "reason": "Missing fresh evidence",
        "supporting_signals": ["metrics_fresh"],
        "action": "none",
    }

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, **kwargs):
            requests.append((endpoint, kwargs["json"]))
            return httpx.Response(
                200,
                request=httpx.Request("POST", endpoint),
                json={
                    "candidates": [
                        {
                            "finishReason": "STOP",
                            "content": {
                                "parts": [{"text": json.dumps(prediction)}],
                            },
                        }
                    ],
                    "usageMetadata": {"promptTokenCount": 20, "candidatesTokenCount": 30},
                },
            )

    monkeypatch.setattr(httpx, "Client", Client)
    result, receipt = qualify.provider_request("gemini", {"metrics_fresh": False}, "test-key")
    assert result.abstained
    assert len(requests) == 1
    assert requests[0][0].endswith("/gemini-3.5-flash-lite:generateContent")
    assert requests[0][1]["generationConfig"]["maxOutputTokens"] == 1024
    assert requests[0][1]["generationConfig"]["responseJsonSchema"] == qualify.SCHEMA
    assert "thinkingConfig" not in requests[0][1]["generationConfig"]
    assert receipt["usage"]["promptTokenCount"] == 20
