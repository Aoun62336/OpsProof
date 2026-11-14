import pytest

from scripts.m6.analyze_capacity import analyze, validate_trial
from scripts.m6.contracts import CATALOG
from scripts.m6.evidence_manifest import hash_evidence
from scripts.m6.verify_scenarios import validate


def make_trial(mode, n, p95):
    return {
        "mode": mode,
        "passed": True,
        "failure": None,
        "timestamp_utc": f"2026-11-{n + 1:02d}T12:00:00+00:00",
        "load_script_sha256": "a" * 64,
        "application_revision": "b" * 40,
        "workload": {
            "count": 2,
            "duration_ms": 250,
            "load_seconds": 10,
            "target_requests_per_second": 1,
            "http_failures": 0,
            "job_p50_seconds": p95 / 2,
            "job_p95_seconds": p95,
            "jobs_per_second": 1 / p95,
            "http_p95_ms": 15,
            "jobs": [
                {"id": f"job-{mode}-{n}-{x}", "status": "completed", "attempts": 1}
                for x in range(2)
            ],
        },
    }


def test_repeated_identical_trials_have_transparent_reduction():
    trials = {
        "fixed": [make_trial("fixed", i, 10) for i in range(3)],
        "hpa": [make_trial("hpa", i, 10) for i in range(3)],
        "keda": [make_trial("keda", i, 5) for i in range(3)],
    }
    result = analyze(trials)
    assert result["keda_vs_fixed_p95_reduction_percent"] == 50
    assert result["source_identity"]["workload"]["count"] == 2


def test_missing_trials_and_mixed_hashes_fail():
    trials = {
        "fixed": [make_trial("fixed", i, 10) for i in range(3)],
        "hpa": [make_trial("hpa", i, 10) for i in range(3)],
        "keda": [make_trial("keda", i, 5) for i in range(2)],
    }
    with pytest.raises(ValueError):
        analyze(trials)
    trials["keda"].append(make_trial("keda", 2, 5))
    trials["keda"][2]["application_revision"] = "c" * 40
    with pytest.raises(ValueError):
        analyze(trials)


def test_retry_or_duplicate_job_is_rejected():
    record = make_trial("fixed", 0, 4)
    record["workload"]["jobs"][0]["attempts"] = 2
    with pytest.raises(ValueError):
        validate_trial(record, "fixed")


def test_evidence_manifest_blocks_credentials_and_escapes(tmp_path):
    good = tmp_path / "evidence.json"
    good.write_text('{"passed":false}')
    assert hash_evidence(tmp_path, [good])["files"][0]["bytes"] > 0
    secret = tmp_path / ".env"
    secret.write_text("secret")
    with pytest.raises(ValueError):
        hash_evidence(tmp_path, [secret])
    with pytest.raises(ValueError):
        hash_evidence(tmp_path, [good, good])


def test_scenario_manifest_does_not_accept_missing_proof():
    records = []
    for scenario, spec in CATALOG.items():
        records.append(
            {
                "scenario": scenario.value,
                "source_revision": "a" * 40,
                "image_digest": "sha256:" + "f" * 64,
                "run_id": f"run-{scenario.value}",
                "environment": "k3d-opsproof",
                "injected_at_utc": "2026-11-08T10:00:00Z",
                "verified_at_utc": "2026-11-08T10:01:00Z",
                "injection_mechanism": spec.mechanism,
                "independent_verification": True,
                "cleanup_verified": True,
                "evidence_files": ["observations.json", "jobs.json"],
            }
        )
    assert validate(records)["metadata_consistent"]
    records[0]["cleanup_verified"] = False
    assert not validate(records)["metadata_consistent"]
