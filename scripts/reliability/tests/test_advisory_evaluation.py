"""Frozen-input, no-retry and interrupted-dispatch safeguards without API calls."""

import json

import pytest

from scripts.reliability import evaluate_advisory as evaluation


@pytest.fixture
def prepared(tmp_path, monkeypatch):
    monkeypatch.setattr(evaluation, "ROOT", tmp_path)
    monkeypatch.setattr(evaluation, "sources", lambda: {"fixture": "frozen-code"})
    monkeypatch.delenv("OPSPROOF_CONTROL_AI_API_KEY", raising=False)
    env = {
        "OPSPROOF_CONTROL_AI_API_KEY": "fixture-key",
        "OPSPROOF_CONTROL_AI_ENABLED": "false",
        "OPSPROOF_CONTROL_AI_PROVIDER": "nvidia",
        "OPSPROOF_CONTROL_AI_MODEL": evaluation.MODEL,
    }
    monkeypatch.setattr(evaluation, "read_env", lambda _path: env)
    directory = evaluation.location()
    directory.mkdir(parents=True)
    connectivity = tmp_path / ".runtime/verification/ai/nvidia-connectivity"
    connectivity.mkdir()
    evaluation.save(
        connectivity / "attempt.json",
        {
            "status": "PASS_CONNECTIVITY_AND_SMALL_JSON_SCHEMA",
            "returned_model": evaluation.SERVING_MODEL,
        },
    )
    requests, labels = [], []
    splits = (
        ["runtime_synthetic"] * 10
        + ["historical_regression"] * 8
        + ["historical_held_out"] * 4
        + ["synthetic_contract"] * 20
    )
    for number, split in enumerate(splits, 1):
        runtime = split == "runtime_synthetic"
        body = evaluation.model_provider.nvidia_body(
            evaluation.MODEL,
            {"metrics_fresh": False},
            system=evaluation.model_provider.SYSTEM if runtime else evaluation.qualify.SYSTEM,
            schema=evaluation.model_provider.SCHEMA if runtime else evaluation.qualify.SCHEMA,
        )
        requests.append(
            {
                "number": number,
                "case_id": f"case-{number}",
                "split": split,
                "body": body,
            }
        )
        labels.append(
            {
                "case_id": f"case-{number}",
                "expected": {"cause": "insufficient_evidence", "action": "none"}
                if runtime
                else {"hypothesis": "unknown", "abstained": True, "action": "none"},
            }
        )
    evaluation.save(directory / "requests.json", {"requests": requests})
    evaluation.save(directory / "labels-private.json", {"labels": labels})
    manifest = {
        "source_sha256": evaluation.sources(),
        "request_ceiling": 42,
        "request_sha256": evaluation.digest(directory / "requests.json"),
        "labels_sha256": evaluation.digest(directory / "labels-private.json"),
        "splits": {split: splits.count(split) for split in set(splits)},
        "route": {
            "endpoint": evaluation.model_provider.NVIDIA_ENDPOINT,
            "requested_model": evaluation.MODEL,
            "registered_serving_model": evaluation.SERVING_MODEL,
        },
    }
    evaluation.save(directory / "manifest.json", manifest)
    evaluation.save(
        directory / "input-review.json",
        {
            "status": "PASS_INPUTS_AND_SAFEGUARDS",
            **{
                name: manifest[name]
                for name in ("source_sha256", "request_sha256", "labels_sha256")
            },
        },
    )
    sleeps = []
    monkeypatch.setattr(evaluation.time, "sleep", sleeps.append)
    return directory, env, sleeps


def good(body, _key):
    runtime = "cause" in body["response_format"]["json_schema"]["schema"].get("properties", {})
    answer = (
        {
            "cause": "insufficient_evidence",
            "action": "none",
            "explanation": "Missing fresh evidence",
            "evidence": ["alert"],
        }
        if runtime
        else {
            "hypothesis": "unknown",
            "abstained": True,
            "reason": "Missing fresh evidence.",
            "supporting_signals": {},
            "action": "none",
        }
    )
    return {
        "status": "RESPONSE_RECEIVED",
        "http_status": 200,
        "registered_serving_model": evaluation.SERVING_MODEL,
        "answer": json.dumps(answer),
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def test_all_42_calls_bounded_and_restart_forbidden(prepared):
    directory, _env, sleeps = prepared
    report = evaluation.execute(transport=good)
    assert report["generation_attempts"] == 42
    assert report["overall_nvidia_attempts"] == 43
    assert report["mechanically_accepted"] == report["contract_correct"] == 42
    assert report["unsafe_actions"] == 0
    assert len(sleeps) == 41 and all(0 < delay <= 6 for delay in sleeps)
    with pytest.raises(ValueError, match="Existing dispatch"):
        evaluation.execute(transport=good)
    assert len(list((directory / "calls").glob("*.json"))) == 42


def test_new_epoch_requires_manifest_review_and_counts_every_prior_attempt(prepared):
    directory, _env, _sleeps = prepared
    run_name = "nvidia-none-validation"
    target = directory.with_name(run_name)
    directory.rename(target)
    manifest = json.loads((target / "manifest.json").read_text())
    manifest.update(
        run_name=run_name, prior_generation_attempts=46, nvidia_total_attempt_ceiling=88
    )
    evaluation.save(target / "manifest.json", manifest)
    calls = []
    with pytest.raises(ValueError, match="independent input"):
        evaluation.execute(run_name=run_name, transport=lambda *args: calls.append(args))
    assert not calls and not (target / "execution-started.json").exists()
    review = json.loads((target / "input-review.json").read_text())
    review["manifest_sha256"] = evaluation.digest(target / "manifest.json")
    evaluation.save(target / "input-review.json", review)
    report = evaluation.execute(run_name=run_name, transport=good)
    assert report["generation_attempts"] == report["contract_correct"] == 42
    assert report["prior_generation_attempts"] == 46
    assert report["overall_nvidia_attempts"] == 88
    assert not (directory / "calls").exists()


def test_copied_approval_cannot_create_another_request_allowance(prepared):
    directory, _env, _sleeps = prepared
    copied = directory.with_name("nvidia-copied-approval")
    copied.mkdir()
    for path in directory.iterdir():
        if path.is_file():
            (copied / path.name).write_bytes(path.read_bytes())
    with pytest.raises(ValueError, match="different run"):
        evaluation.execute(
            run_name=copied.name, transport=lambda *_: pytest.fail("No dispatch allowed")
        )
    assert not (copied / "execution-started.json").exists()


@pytest.mark.parametrize("run_name", ["../escape", "C:/escape", "nvidia/escape", ""])
def test_run_name_cannot_escape_evidence_directory(run_name):
    with pytest.raises(ValueError, match="run name"):
        evaluation.location(run_name)


def test_changed_parent_proof_prevents_dispatch(prepared):
    directory, _env, _sleeps = prepared
    parent = directory.parent / "parent.json"
    evaluation.save(parent, {"original": True})
    manifest = json.loads((directory / "manifest.json").read_text())
    manifest["parent_proof_sha256"] = {
        str(parent.relative_to(evaluation.ROOT)): evaluation.digest(parent)
    }
    evaluation.save(directory / "manifest.json", manifest)
    evaluation.save(parent, {"original": False})
    with pytest.raises(ValueError, match="Parent evidence changed"):
        evaluation.execute(transport=lambda *_: pytest.fail("No dispatch allowed"))


def test_http_failure_stops_batch_without_retry(prepared):
    calls = []
    report = evaluation.execute(
        transport=lambda *args: calls.append(args) or {"status": "HTTP_FAILURE", "http_status": 429}
    )
    assert len(calls) == report["generation_attempts"] == 1
    assert not report["complete"]


@pytest.mark.parametrize(
    "change,stop_reason",
    [
        ({"explanation": ""}, "MECHANICAL_VALIDATION_FAILED"),
        ({"evidence": ["alert", "alert"]}, "MECHANICAL_VALIDATION_FAILED"),
        ({"cause": "api_unreachable"}, "CONTRACT_MISMATCH"),
        ({"action": "resume_demo_worker"}, "UNSAFE_ACTION"),
    ],
)
def test_first_failed_gate_stops_and_preserves_receipt(prepared, change, stop_reason):
    directory, _env, sleeps = prepared
    calls = []

    def response(body, key):
        calls.append(body)
        row = good(body, key)
        row["answer"] = json.dumps({**json.loads(row["answer"]), **change})
        return row

    report = evaluation.execute(transport=response)
    assert len(calls) == report["generation_attempts"] == 1
    assert not sleeps and not report["complete"]
    assert report["stop_reason"] == stop_reason
    receipt = json.loads((directory / "calls/001.json").read_text())
    assert receipt["stop_reason"] == stop_reason
    assert all(json.loads(receipt["answer"])[name] == value for name, value in change.items())
    assert len(list((directory / "calls").glob("*.json"))) == 1
    with pytest.raises(ValueError, match="Existing dispatch"):
        evaluation.execute(transport=response)
    assert len(calls) == 1


@pytest.mark.parametrize("identity", [None, "private/nvidia/different-model"])
def test_unexpected_serving_identity_stops(prepared, identity):
    def response(body, key):
        return {**good(body, key), "registered_serving_model": identity}

    report = evaluation.execute(transport=response)
    assert report["generation_attempts"] == 1
    assert report["mechanically_accepted"] == 0


def test_interruption_counts_reserved_request_and_cannot_restart(prepared):
    directory, _env, _sleeps = prepared

    def interrupt(*_args):
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        evaluation.execute(transport=interrupt)
    row = json.loads((directory / "calls/001.json").read_text())
    assert row["status"] == "DISPATCH_RESERVED_OUTCOME_UNKNOWN"
    assert (
        json.loads((directory / "execution-result.json").read_text())["overall_nvidia_attempts"]
        == 2
    )
    with pytest.raises(ValueError, match="Existing dispatch"):
        evaluation.execute(transport=good)


def test_missing_receipt_does_not_allow_restart(prepared):
    directory, _env, _sleeps = prepared
    evaluation.execute(transport=lambda *_args: {"status": "HTTP_FAILURE", "http_status": 503})
    (directory / "calls/001.json").unlink()
    with pytest.raises(FileExistsError):
        evaluation.execute(transport=good)


@pytest.mark.parametrize("filename", ["requests.json", "labels-private.json"])
def test_changed_frozen_inputs_fail_before_network(prepared, filename):
    directory, _env, _sleeps = prepared
    with (directory / filename).open("a") as stream:
        stream.write(" ")
    with pytest.raises(ValueError, match="Frozen inputs changed"):
        evaluation.execute(transport=good)
    assert not (directory / "execution-started.json").exists()


def test_changed_source_fails_before_network(prepared, monkeypatch):
    directory, _env, _sleeps = prepared
    monkeypatch.setattr(evaluation, "sources", lambda: {"fixture": "changed"})
    with pytest.raises(ValueError, match="source changed"):
        evaluation.execute(transport=good)
    assert not (directory / "execution-started.json").exists()


def test_enabled_runtime_is_rejected_before_network(prepared):
    directory, env, _sleeps = prepared
    env["OPSPROOF_CONTROL_AI_ENABLED"] = "true"
    with pytest.raises(ValueError, match="disabled runtime"):
        evaluation.execute(transport=good)
    assert not (directory / "execution-started.json").exists()


def test_missing_independent_review_is_rejected(prepared):
    directory, _env, _sleeps = prepared
    evaluation.save(directory / "input-review.json", {"status": "PASS_INPUTS_AND_SAFEGUARDS"})
    with pytest.raises(ValueError, match="independent input"):
        evaluation.execute(transport=good)


def test_invented_evidence_path_is_not_accepted(prepared):
    directory, _env, _sleeps = prepared
    _manifest, requests, labels = evaluation.check()
    spec, label = requests[10], labels[10]
    row = good(spec["body"], "fixture-key")
    answer = json.loads(row["answer"])
    answer["supporting_signals"] = ["invented.path"]
    row["answer"] = json.dumps(answer)
    evaluation.validate(row, spec, label)
    assert row["mechanically_accepted"] is False


@pytest.mark.parametrize("reason", ["Unfinished claim=", "x" * 500, "", "   "])
def test_unfinished_explanation_is_not_accepted(prepared, reason):
    _manifest, requests, labels = evaluation.check()
    spec, label = requests[10], labels[10]
    row = good(spec["body"], "fixture-key")
    raw = json.loads(row["answer"])
    raw["reason"] = reason
    row["answer"] = json.dumps(raw)
    evaluation.validate(row, spec, label)
    assert row["mechanically_accepted"] is False


@pytest.mark.parametrize("path", ["context.story", "evidence_contract.units", "other_case.value"])
def test_citation_must_match_this_requests_wire_allowlist(prepared, path):
    _manifest, requests, labels = evaluation.check()
    spec, label = requests[10], labels[10]
    facts = {
        "metrics_fresh": False,
        "context": {"story": "not a measurement"},
        "evidence_contract": {"units": "metadata"},
        "observation": {"db_probe_ok": None},
    }
    spec["body"] = evaluation.model_provider.nvidia_body(
        evaluation.MODEL, facts, system=evaluation.qualify.SYSTEM, schema=evaluation.qualify.SCHEMA
    )
    row = good(spec["body"], "fixture-key")
    raw = json.loads(row["answer"])
    raw["supporting_signals"][path] = True
    row["answer"] = json.dumps(raw)
    evaluation.validate(row, spec, label)
    assert row["mechanically_accepted"] is False


@pytest.mark.parametrize("path", ["observation", "observation.db_probe_ok"])
def test_existing_parent_and_present_null_citations_remain_valid(prepared, path):
    _manifest, requests, labels = evaluation.check()
    spec, label = requests[10], labels[10]
    facts = {"metrics_fresh": False, "observation": {"db_probe_ok": None}}
    spec["body"] = evaluation.model_provider.nvidia_body(
        evaluation.MODEL, facts, system=evaluation.qualify.SYSTEM, schema=evaluation.qualify.SCHEMA
    )
    row = good(spec["body"], "fixture-key")
    raw = json.loads(row["answer"])
    raw["supporting_signals"][path] = True
    row["answer"] = json.dumps(raw)
    evaluation.validate(row, spec, label)
    assert row["mechanically_accepted"] is True


@pytest.mark.parametrize(
    "selection,accepted", [({}, False), ({"observation.db_probe_ok": True}, True)]
)
def test_positive_wire_branch_requires_at_least_one_citation(prepared, selection, accepted):
    _manifest, requests, _labels = evaluation.check()
    spec = requests[10]
    facts = {"observation": {"db_probe_ok": False, "db_connection_errors": 7}}
    spec["body"] = evaluation.model_provider.nvidia_body(
        evaluation.MODEL, facts, system=evaluation.qualify.SYSTEM, schema=evaluation.qualify.SCHEMA
    )
    label = {
        "expected": {"hypothesis": "database_connectivity", "abstained": False, "action": "none"}
    }
    row = good(spec["body"], "fixture-key")
    raw = {
        **json.loads(row["answer"]),
        **label["expected"],
        "reason": "The probe failed with seven connection errors.",
        "supporting_signals": selection,
    }
    row["answer"] = json.dumps(raw)
    evaluation.validate(row, spec, label)
    assert row["mechanically_accepted"] is accepted
    assert row["contract_correct"] is accepted
    assert json.loads(row["answer"]) == raw  # No citations are inserted after generation.


@pytest.mark.parametrize("mutation", ["missing_action", "token_overrun"])
def test_missing_explicit_action_and_token_overrun_are_rejected(prepared, mutation):
    _manifest, requests, labels = evaluation.check()
    spec, label = requests[10], labels[10]
    row = good(spec["body"], "fixture-key")
    if mutation == "missing_action":
        answer = json.loads(row["answer"])
        del answer["action"]
        row["answer"] = json.dumps(answer)
    else:
        row["usage"] = {
            "prompt_tokens": 1,
            "completion_tokens": spec["body"]["max_tokens"] + 1,
            "total_tokens": spec["body"]["max_tokens"] + 2,
        }
    evaluation.validate(row, spec, label)
    assert row["mechanically_accepted"] is False


@pytest.mark.parametrize("wrapped", [False, True])
def test_error_retention_strips_active_key_and_details(monkeypatch, wrapped):
    class Response:
        status_code = 503

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_bytes(self):
            error = {
                "code": 503,
                "message": "fixture-key https://secret.invalid account@example.com",
                "details": ["private"],
            }
            yield json.dumps({"error": error} if wrapped else error).encode()

    class Client:
        def __init__(self, **kwargs):
            assert kwargs["trust_env"] is kwargs["follow_redirects"] is False

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def stream(self, method, endpoint, **kwargs):
            assert method == "POST" and endpoint == evaluation.model_provider.NVIDIA_ENDPOINT
            return Response()

    monkeypatch.setattr(evaluation.httpx, "Client", Client)
    result = evaluation.send({}, "fixture-key")
    assert result["status"] == "HTTP_FAILURE"
    assert "fixture-key" not in json.dumps(result)
    assert "secret.invalid" not in json.dumps(result)
    assert "details" not in result["error"]


def test_incomplete_response_retains_only_safe_diagnostic_metadata(monkeypatch):
    class Response:
        status_code = 200

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def iter_bytes(self):
            yield json.dumps(
                {
                    "model": evaluation.SERVING_MODEL,
                    "usage": {
                        "prompt_tokens": 3,
                        "completion_tokens": 4096,
                        "total_tokens": 4099,
                    },
                    "choices": [
                        {
                            "finish_reason": "length",
                            "message": {
                                "content": "",
                                "reasoning_content": "do not retain internal reasoning fixture-key",
                            },
                        }
                    ],
                }
            ).encode()

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def stream(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr(evaluation.httpx, "Client", Client)
    result = evaluation.send({}, "fixture-key")
    assert result["finish_reason"] == "length"
    assert result["parse_error_reason"] == "Model response incomplete or blocked"
    assert result["usage"]["completion_tokens"] == 4096
    assert "answer" not in result
    assert "reasoning_content" not in result
    assert result["content_characters"] == 0
    assert result["reasoning_content_characters"] == len(
        "do not retain internal reasoning fixture-key"
    )
    assert "do not retain internal reasoning" not in json.dumps(result)
    assert "fixture-key" not in json.dumps(result)


@pytest.mark.parametrize("count,valid", [(-1, False), (11, False), (0, True), (10, True)])
def test_reasoning_token_metadata_is_bounded_by_reported_completion(monkeypatch, count, valid):
    from unittest.mock import MagicMock

    data = {
        "model": evaluation.SERVING_MODEL,
        "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
        "usage": {
            "prompt_tokens": 1,
            "completion_tokens": 10,
            "total_tokens": 11,
            "completion_tokens_details": {"reasoning_tokens": count},
        },
    }
    factory = MagicMock()
    response = (
        factory.return_value.__enter__.return_value.stream.return_value.__enter__.return_value
    )
    response.status_code = 200
    response.iter_bytes.return_value = [json.dumps(data).encode()]
    monkeypatch.setattr(evaluation.httpx, "Client", factory)
    row = evaluation.send({}, "fixture-key")
    assert row["reasoning_tokens_metadata_valid"] is valid
    assert ("reported_reasoning_tokens" in row) is valid
    if valid:
        assert row["reported_reasoning_tokens"] == count
