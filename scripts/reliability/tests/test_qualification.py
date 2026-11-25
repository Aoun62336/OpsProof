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


@pytest.mark.parametrize("name", ["groq", "gemini", "nvidia"])
def test_offline_qualification_rejects_external_execution(name):
    with pytest.raises(ValueError, match="External benchmark execution is retired"):
        benchmark({}, provider=name)
