"""Evidence semantics and citation safeguards without external model calls."""

import json

import pytest
from scripts.reliability import qualify

from opsproof_control import model_provider
from opsproof_control.benchmark import CASES, make_snapshot
from opsproof_control.diagnosis import model_facts
from opsproof_control.reliability_diagnosis import Finding


@pytest.mark.parametrize("duplicated", [False, True])
def test_link_uniqueness_is_visible_without_exposing_identifiers(duplicated):
    snapshot = make_snapshot(CASES[0])
    if duplicated:
        snapshot.job_ids.append(snapshot.job_ids[0])
    facts = model_facts(snapshot)
    assert facts["linked_jobs_unique"] is (not duplicated)
    assert facts["linked_job_count"] == len(snapshot.job_ids)
    serialized = json.dumps(facts)
    assert str(snapshot.run_id) not in serialized
    assert all(str(job_id) not in serialized for job_id in snapshot.job_ids)
    assert snapshot.incident_fingerprint not in serialized


def test_missing_queue_is_distinct_from_observed_zero():
    missing = make_snapshot(CASES[-1])
    empty = make_snapshot(CASES[4])
    assert model_facts(missing)["queued"] is None
    assert model_facts(empty)["queued"] == 0
    assert "not consumer count" in model_facts(empty)["evidence_contract"]["processing"]


def test_runtime_rejects_duplicate_evidence_references():
    answer = json.dumps(
        {
            "cause": "insufficient_evidence",
            "action": "none",
            "explanation": "Missing metrics",
            "evidence": ["queue", "queue"],
        }
    )
    with pytest.raises(ValueError, match="duplicate evidence"):
        model_provider.diagnosis_output(answer)


def test_reliability_rejects_duplicate_field_paths():
    result = Finding(
        hypothesis="unknown",
        abstained=True,
        reason="Missing metrics",
        supporting_signals=["metrics_fresh", "metrics_fresh"],
    )
    with pytest.raises(ValueError, match="duplicate evidence"):
        qualify.validate_evidence_paths(result, {"metrics_fresh": False})


def test_provider_schema_contains_the_local_explanation_bounds():
    assert qualify.SCHEMA["properties"]["reason"]["maxLength"] == 500
    assert qualify.SCHEMA["properties"]["reason"]["minLength"] == 1
    assert qualify.SCHEMA["properties"]["supporting_signals"]["maxItems"] == 6
    assert qualify.SCHEMA["properties"]["supporting_signals"]["uniqueItems"] is True
    branches = qualify.SCHEMA["oneOf"]
    assert branches[0]["properties"]["abstained"]["const"] is True
    assert branches[0]["properties"]["hypothesis"]["const"] == "unknown"
    assert branches[1]["properties"]["abstained"]["const"] is False
    assert "unknown" not in branches[1]["properties"]["hypothesis"]["enum"]
