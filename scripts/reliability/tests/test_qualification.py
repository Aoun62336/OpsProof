import json
from pathlib import Path

import pytest

from scripts.reliability import qualify
from scripts.reliability.qualify import benchmark

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


def test_evidence_contract_preserves_inputs_units_and_replay_clock():
    original = {
        "evaluation_at": "2026-11-14T10:00:00+00:00",
        "observation": {
            "observed_at": "2026-11-14T09:59:55+00:00",
            "metrics_fresh": True,
            "queue_lag": 52,
        },
    }
    before = json.dumps(original, sort_keys=True)
    facts = qualify.provider_facts(original)
    assert json.dumps(original, sort_keys=True) == before
    contract = facts["evidence_contract"]
    assert "undelivered Redis Stream job messages" in contract["units"]["queue_lag"]
    assert contract["freshness"]["observation_age_seconds"] == 5
    assert contract["freshness"]["metrics_fresh_at_reference"] is True
    assert contract["signature_thresholds"]["worker_saturation"]["queue_lag_min_messages"] == 10
    assert contract["signature_thresholds"]["worker_saturation"]["queue_age_min_seconds"] == 5
    assert "Production SLO thresholds are unavailable" in contract["threshold_scope"]


@pytest.mark.parametrize(
    "timestamp", [None, "invalid", "2026-11-14T10:00:01+00:00", "2026-11-14T09:58:59+00:00"]
)
def test_missing_future_and_stale_metrics_are_explicitly_unusable(timestamp):
    facts = qualify.provider_facts(
        {
            "evaluation_at": "2026-11-14T10:00:00+00:00",
            "observation": {"observed_at": timestamp, "metrics_fresh": True},
        }
    )
    assert facts["evidence_contract"]["freshness"]["metrics_fresh_at_reference"] is False


@pytest.mark.parametrize("path", ["observation.queue_lag", "samples.0.value"])
def test_exact_evidence_paths_resolve_without_evaluating_code(path):
    finding = qualify.Finding(
        hypothesis="unknown", abstained=True, reason="review", supporting_signals=[path]
    )
    qualify.validate_evidence_paths(
        finding, {"observation": {"queue_lag": 0}, "samples": [{"value": False}]}
    )


@pytest.mark.parametrize(
    "path",
    [
        "recorded_evidence.downstream_timeouts",
        "observation.missing",
        "samples.1.value",
        "samples.-1.value",
        "",
        "__class__",
    ],
)
def test_missing_citations_fail_closed(path):
    finding = qualify.Finding(
        hypothesis="unknown", abstained=True, reason="review", supporting_signals=[path]
    )
    with pytest.raises(ValueError, match="evidence"):
        qualify.validate_evidence_paths(
            finding,
            {
                "observation": {"downstream_timeouts": 1, "queue_age_seconds": None},
                "recorded_evidence": {},
                "samples": [{"value": 0}],
            },
        )


def test_provider_response_rejects_invented_path_through_normal_entry(monkeypatch):
    import httpx2 as httpx

    calls = []

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def post(self, endpoint, **kwargs):
            calls.append(kwargs["json"])
            return httpx.Response(
                200,
                request=httpx.Request("POST", endpoint),
                json={
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {
                                "content": json.dumps(
                                    {
                                        "hypothesis": "unknown",
                                        "abstained": True,
                                        "reason": "review",
                                        "supporting_signals": ["invented.path"],
                                        "action": "none",
                                    }
                                )
                            },
                        }
                    ],
                },
            )

    monkeypatch.setattr(httpx, "Client", Client)
    with pytest.raises(ValueError, match="missing evidence path"):
        qualify.provider_request("groq", {"metrics_fresh": False}, "test-key")
    assert len(calls) == 1
    submitted = json.loads(calls[0]["messages"][1]["content"])
    assert submitted["evidence_contract"]["units"]["queue_lag"].startswith("undelivered")


def test_null_collector_status_can_support_abstention():
    finding = qualify.Finding(
        hypothesis="unknown",
        abstained=True,
        reason="Collector status unavailable",
        supporting_signals=["recorded_evidence.metrics_collector_http_status"],
    )
    qualify.validate_evidence_paths(
        finding, {"recorded_evidence": {"metrics_collector_http_status": None}}
    )


def test_frozen_held_out_cases_and_independent_labels_offline():
    import hashlib
    from datetime import datetime

    from opsproof_control.reliability_diagnosis import Observation, deterministic_reliability

    directory = DATASET.parent / "capacity_held_out_v1"
    hashes = json.loads((directory / "sha256.json").read_text())
    for name, expected in hashes.items():
        assert hashlib.sha256((directory / name).read_bytes()).hexdigest() == expected
    visible = json.loads((directory / "model-visible.json").read_text())
    private = json.loads((directory / "ground-truth-private.json").read_text())
    assert private["independent_reviewer"] == "/root/ground_truth_review"
    assert len(visible["cases"]) == len(private["cases"]) == 4
    for case, label in zip(visible["cases"], private["cases"], strict=True):
        assert case["id"] == label["id"]
        assert set(case) == {"id", "facts"}
        assert "expected_hypothesis" not in json.dumps(case)
        observation = Observation.model_validate_json(json.dumps(case["facts"]["observation"]))
        finding = deterministic_reliability(
            observation, now=datetime.fromisoformat(case["facts"]["evaluation_at"])
        )
        assert finding.hypothesis == label["expected_hypothesis"]
        assert finding.abstained == label["expected_abstained"]
        assert finding.action == "none"
