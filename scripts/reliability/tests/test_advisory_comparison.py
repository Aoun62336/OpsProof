"""Request authorization, frozen inputs and interrupted-call bounds without APIs."""

import hashlib
import json
from collections import Counter

import pytest
from opsproof_control.reliability_diagnosis import Finding

from scripts.reliability import compare_advisory as compare
from scripts.reliability import qualify


def fixture(directory):
    rows = [
        {
            "id": f"case-{i}",
            "split": "regression" if i < 8 else "held_out",
            "facts": qualify.provider_facts(
                {
                    "evaluation_at": "2026-11-01T00:00:00Z",
                    "observation": {"observed_at": "2026-11-01T00:00:00Z", "metrics_fresh": False},
                }
            ),
        }
        for i in range(12)
    ]
    labels = [
        {
            "id": row["id"],
            "split": row["split"],
            "expected_hypothesis": "unknown",
            "expected_abstained": True,
        }
        for row in rows
    ]
    for name, value in (
        ("requests.json", {"cases": rows}),
        ("labels-private.json", {"cases": labels}),
    ):
        compare.write(directory / name, value)
    manifest = {
        "cases": 12,
        "request_ceiling": 24,
        "automatic_retries": 0,
        "fallbacks": 0,
        "models": {"groq": qualify.GROQ_MODEL, "gemini": qualify.GEMINI_MODEL},
        "request_file_sha256": compare.digest(directory / "requests.json"),
        "labels_file_sha256": compare.digest(directory / "labels-private.json"),
        "provider_code_sha256": compare.digest(compare.ROOT / "scripts/reliability/qualify.py"),
        "prompt_sha256": hashlib.sha256(qualify.SYSTEM.encode()).hexdigest(),
        "schema_sha256": hashlib.sha256(
            json.dumps(qualify.SCHEMA, sort_keys=True).encode()
        ).hexdigest(),
    }
    compare.write(directory / "manifest.json", manifest)
    return manifest


def test_twenty_four_requests_and_no_restart_after_dispatch(tmp_path, monkeypatch):
    manifest = fixture(tmp_path)
    calls = []

    def provider(name, _facts, _key, *, receipt):
        calls.append(name)
        receipt["http_status"] = 200
        return Finding(
            hypothesis="unknown", abstained=True, reason="fixture", supporting_signals=[]
        ), receipt

    monkeypatch.setattr(qualify, "provider_request", provider)
    monkeypatch.setattr(compare.time, "sleep", lambda _seconds: None)
    report = compare.execute(
        tmp_path, manifest["request_file_sha256"], {"groq": "fixture", "gemini": "fixture"}
    )
    assert report["external_requests_issued"] == 24
    assert Counter(calls) == {"groq": 12, "gemini": 12}
    with pytest.raises(FileExistsError):
        compare.execute(
            tmp_path, manifest["request_file_sha256"], {"groq": "fixture", "gemini": "fixture"}
        )
    assert len(calls) == 24


def test_http_rejection_stops_that_provider_without_retry(tmp_path, monkeypatch):
    manifest = fixture(tmp_path)
    calls = []

    def provider(name, _facts, _key, *, receipt):
        calls.append(name)
        if name == "groq":
            receipt["http_status"] = 429
            raise RuntimeError("fixture quota rejection")
        receipt["http_status"] = 200
        return Finding(
            hypothesis="unknown", abstained=True, reason="fixture", supporting_signals=[]
        ), receipt

    monkeypatch.setattr(qualify, "provider_request", provider)
    monkeypatch.setattr(compare.time, "sleep", lambda _seconds: None)
    result = compare.execute(
        tmp_path, manifest["request_file_sha256"], {"groq": "fixture", "gemini": "fixture"}
    )
    assert result["external_requests_issued"] == 13
    assert Counter(calls) == {"groq": 1, "gemini": 12}
    assert result["stopped_providers"]["groq"]["http_status"] == 429


def test_unknown_interrupted_outcome_is_reserved_and_never_reissued(tmp_path, monkeypatch):
    manifest = fixture(tmp_path)
    calls = []

    def interrupted(*_args, **_kwargs):
        calls.append(True)
        raise KeyboardInterrupt

    monkeypatch.setattr(qualify, "provider_request", interrupted)
    with pytest.raises(KeyboardInterrupt):
        compare.execute(
            tmp_path, manifest["request_file_sha256"], {"groq": "fixture", "gemini": "fixture"}
        )
    assert (
        json.loads(next((tmp_path / "calls").iterdir()).read_text(encoding="utf-8"))["status"]
        == "ISSUED_OUTCOME_UNKNOWN"
    )
    with pytest.raises(FileExistsError):
        compare.execute(
            tmp_path, manifest["request_file_sha256"], {"groq": "fixture", "gemini": "fixture"}
        )
    assert len(calls) == 1


def test_hash_mismatch_and_missing_confirmation_never_read_keys_or_call_provider(
    tmp_path, monkeypatch
):
    fixture(tmp_path)
    monkeypatch.setattr(
        compare, "read_env", lambda _path: pytest.fail("Credentials read before authorization")
    )
    monkeypatch.setattr(
        qualify, "provider_request", lambda *_a, **_k: pytest.fail("Unexpected API call")
    )
    monkeypatch.setattr("sys.argv", ["compare", "--inputs", str(tmp_path), "--execute"])
    with pytest.raises(SystemExit):
        compare.main()
    with pytest.raises(ValueError):
        compare.execute(tmp_path, "incorrect-hash", {"groq": "fixture", "gemini": "fixture"})
    with (tmp_path / "requests.json").open("a", encoding="utf-8") as stream:
        stream.write(" ")
    with pytest.raises(ValueError):
        compare.inputs(tmp_path)
