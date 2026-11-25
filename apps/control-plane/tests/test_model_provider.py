"""Provider contract checks without contacting an external API."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx2 as httpx
import pytest

from opsproof_control import model_provider as provider
from opsproof_control.benchmark import CASES, make_snapshot
from opsproof_control.diagnosis import deterministic


def configure(monkeypatch, name="nvidia"):
    monkeypatch.setattr(
        provider,
        "settings",
        lambda: SimpleNamespace(
            ai_enabled=True,
            ai_api_key="test-key",
            ai_provider=name,
            ai_model="nvidia/nemotron-3.5-super-vl-120b-a12b" if name == "nvidia" else "test-model",
        ),
    )


def test_disabled_provider_never_calls_network(monkeypatch):
    monkeypatch.setattr(provider, "settings", lambda: SimpleNamespace(ai_enabled=False))
    factory = MagicMock()
    monkeypatch.setattr(provider.httpx, "Client", factory)
    with pytest.raises(ValueError):
        provider.compare(make_snapshot(CASES[0]))
    factory.assert_not_called()


@pytest.mark.parametrize("name", ["openai", "nvidia"])
@pytest.mark.parametrize("malicious", [False, True])
def test_structured_provider_output(monkeypatch, name, malicious):
    configure(monkeypatch, name)
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
            "model": provider.NVIDIA_SERVING_MODEL,
            "choices": [{"finish_reason": "stop", "message": {"content": output}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30},
        }
    )
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.post.return_value = httpx.Response(
        200, request=httpx.Request("POST", "https://example.invalid"), json=data
    )
    monkeypatch.setattr(provider.httpx, "Client", factory)
    if malicious:
        with pytest.raises(ValueError):
            provider.compare(snapshot)
    else:
        result = provider.compare(snapshot)
        assert result["usage"] == {"input_tokens": 20, "output_tokens": 30}
        assert result["diagnosis"] == diagnosis
    body = client.post.call_args.kwargs["json"]
    assert snapshot.incident_fingerprint not in json.dumps(body)
    assert str(snapshot.job_ids[0]) not in json.dumps(body)
    assert "tools" not in body
    assert factory.call_args.kwargs["follow_redirects"] is False
    assert factory.call_args.kwargs["trust_env"] is False
    if name == "nvidia":
        assert client.post.call_args.args == (
            "https://integrate.api.nvidia.com/v1/chat/completions",
        )
        assert body["stream"] is False
        assert body["max_tokens"] == provider.NVIDIA_MAX_OUTPUT_TOKENS == 8192
        assert body["reasoning_effort"] == provider.NVIDIA_REASONING_EFFORT == "low"
        assert body["temperature"] == provider.NVIDIA_TEMPERATURE == 1.0
        assert body["top_p"] == provider.NVIDIA_TOP_P == 0.95
        assert body["seed"] == provider.NVIDIA_SEED == 42
        wire_schema = body["response_format"]["json_schema"]["schema"]
        assert wire_schema == provider.nvidia_schema(provider.SCHEMA)
        assert "uniqueItems" not in wire_schema["properties"]["evidence"]
        assert provider.SCHEMA["properties"]["evidence"]["uniqueItems"] is True


@pytest.mark.parametrize("name", ["gemini", "groq"])
def test_retired_providers_rejected_before_network(monkeypatch, name):
    configure(monkeypatch, name)
    factory = MagicMock()
    monkeypatch.setattr(provider.httpx, "Client", factory)
    with pytest.raises(ValueError, match="Unsupported AI provider"):
        provider.compare(make_snapshot(CASES[0]))
    factory.assert_not_called()


@pytest.mark.parametrize(
    "status,data",
    [
        (202, {}),
        (200, {"choices": [{"finish_reason": "length", "message": {"content": "{}"}}]}),
        (
            200,
            {
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "{}", "tool_calls": [{}]}}
                ]
            },
        ),
        (200, {"choices": []}),
        (503, {"error": {"message": "unavailable"}}),
    ],
)
def test_nvidia_incomplete_or_error_never_retried(monkeypatch, status, data):
    configure(monkeypatch)
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.post.return_value = httpx.Response(
        status,
        request=httpx.Request("POST", "https://example.invalid"),
        json={"model": provider.NVIDIA_SERVING_MODEL, **data},
    )
    monkeypatch.setattr(provider.httpx, "Client", factory)
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        provider.compare(make_snapshot(CASES[0]))
    assert client.post.call_count == 1


@pytest.mark.parametrize("model", [None, "private/nvidia/unexpected"])
def test_nvidia_serving_identity_is_pinned(model):
    with pytest.raises(ValueError, match="serving identity"):
        provider.nvidia_output({"model": model})


def test_nvidia_rejects_deprecated_function_call():
    with pytest.raises(ValueError, match="ambiguous"):
        provider.nvidia_output(
            {
                "model": provider.NVIDIA_SERVING_MODEL,
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "{}", "function_call": {}}}
                ],
            }
        )


def test_nvidia_wire_translation_preserves_original_nested_contract():
    original = {
        "oneOf": [
            {
                "properties": {
                    "citations": {
                        "type": "array",
                        "uniqueItems": True,
                        "maxItems": 6,
                        "items": {"type": "string", "maxLength": 500},
                    }
                }
            }
        ]
    }
    before = json.dumps(original, sort_keys=True)
    wire = provider.nvidia_schema(original)
    assert json.dumps(original, sort_keys=True) == before
    citations = wire["oneOf"][0]["properties"]["citations"]
    assert "uniqueItems" not in citations
    assert citations["maxItems"] == 6
    assert citations["items"]["maxLength"] == 500


def test_nvidia_alternatives_preserve_every_required_response_field():
    from scripts.reliability import qualify

    before = json.dumps(qualify.SCHEMA, sort_keys=True)
    wire = provider.nvidia_schema(qualify.SCHEMA)
    assert json.dumps(qualify.SCHEMA, sort_keys=True) == before
    for alternative in wire["oneOf"]:
        assert alternative["type"] == "object"
        assert alternative["additionalProperties"] is False
        assert set(alternative["required"]) == set(qualify.SCHEMA["required"])
        assert set(alternative["properties"]) == set(qualify.SCHEMA["properties"])
        assert alternative["properties"]["reason"]["maxLength"] == 500
        assert alternative["properties"]["action"]["enum"] == ["none"]
    assert wire["oneOf"][0]["properties"]["hypothesis"]["const"] == "unknown"
    assert wire["oneOf"][0]["properties"]["abstained"]["const"] is True
    assert wire["oneOf"][1]["properties"]["abstained"]["const"] is False


@pytest.mark.parametrize(
    "container", ["properties", "$defs", "definitions", "patternProperties", "dependentSchemas"]
)
def test_nvidia_schema_preserves_names_in_schema_maps(container):
    schema = {container: {"uniqueItems": {"type": "array", "uniqueItems": True}}}
    assert provider.nvidia_schema(schema) == {container: {"uniqueItems": {"type": "array"}}}
    assert schema[container]["uniqueItems"]["uniqueItems"] is True


@pytest.mark.parametrize("keyword", ["const", "enum", "default", "examples"])
def test_nvidia_schema_preserves_literal_data(keyword):
    literal = {"uniqueItems": True, "properties": {"uniqueItems": "ordinary data"}}
    schema = {keyword: [literal] if keyword in ("enum", "examples") else literal}
    wire = provider.nvidia_schema(schema)
    assert wire == schema
    wire[keyword].clear()
    assert schema[keyword]


def test_nvidia_schema_rejects_constraint_override():
    schema = {
        "type": "object",
        "properties": {"reason": {"type": "string", "maxLength": 50}},
        "oneOf": [{"properties": {"reason": {"maxLength": 500}}}],
    }
    with pytest.raises(ValueError, match="constraint intersection: maxLength"):
        provider.nvidia_schema(schema)


def test_runtime_wire_evidence_has_only_canonical_unique_subsets():
    evidence = provider.nvidia_schema(provider.SCHEMA)["properties"]["evidence"]
    assert len(evidence["enum"]) == 64
    assert [] in evidence["enum"]
    assert ["alert", "queue"] in evidence["enum"]
    assert ["queue", "queue"] not in evidence["enum"]
    assert all(len(group) == len(set(group)) <= 6 for group in evidence["enum"])
    assert "uniqueItems" not in evidence
    assert provider.SCHEMA["properties"]["evidence"]["uniqueItems"] is True


def test_bounded_subset_translation_preserves_existing_enum_and_minimum():
    schema = {
        "type": "array",
        "items": {"enum": ["a", "b"]},
        "uniqueItems": True,
        "minItems": 1,
        "maxItems": 1,
        "enum": [["b"]],
    }
    assert provider.nvidia_schema(schema)["enum"] == [["b"]]


@pytest.mark.parametrize("case", CASES, ids=lambda case: case[0])
def test_grounding_guard_accepts_matching_policy_and_rejects_wrong_cause(case):
    snapshot = make_snapshot(case)
    correct = deterministic(snapshot)
    assert provider.grounded_diagnosis(correct.model_dump_json(), snapshot) == correct
    wrong = correct.model_dump()
    wrong["cause"] = (
        "api_unreachable" if correct.cause != "api_unreachable" else "demo_worker_paused"
    )
    with pytest.raises(ValueError, match="contradicts verified operational policy"):
        provider.grounded_diagnosis(json.dumps(wrong), snapshot)


def test_grounding_guard_rejects_observed_unsafe_unsupported_alert_answer():
    snapshot = make_snapshot(next(case for case in CASES if case[0] == "unsupported_alert"))
    observed = {
        "action": "resume_demo_worker",
        "cause": "demo_worker_paused",
        "evidence": ["alert", "worker_hold", "job_ids"],
        "explanation": "The alert is firing and linked run conditions are satisfied.",
    }
    # A structurally valid answer is insufficient; the actual unsupported action must fail.
    provider.diagnosis_output(json.dumps(observed))
    with pytest.raises(ValueError, match="contradicts verified operational policy"):
        provider.grounded_diagnosis(json.dumps(observed), snapshot)


def test_runtime_compare_uses_grounding_guard(monkeypatch):
    configure(monkeypatch)
    snapshot = make_snapshot(next(case for case in CASES if case[0] == "unsupported_alert"))
    unsafe = deterministic(make_snapshot(CASES[0])).model_dump_json()
    factory = MagicMock()
    client = factory.return_value.__enter__.return_value
    client.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", "https://example.invalid"),
        json={
            "model": provider.NVIDIA_SERVING_MODEL,
            "choices": [{"finish_reason": "stop", "message": {"content": unsafe}}],
        },
    )
    monkeypatch.setattr(provider.httpx, "Client", factory)
    with pytest.raises(ValueError, match="contradicts verified operational policy"):
        provider.compare(snapshot)
    assert client.post.call_count == 1


def test_per_request_citation_schema_contains_existing_paths_only():
    from scripts.reliability import qualify

    facts = {"observation": {"queue_lag": 0, "db_probe_ok": None}, "samples": [{"value": False}]}
    before = json.dumps(qualify.SCHEMA, sort_keys=True)
    body = provider.nvidia_body(
        provider.NVIDIA_MODEL, facts, system=qualify.SYSTEM, schema=qualify.SCHEMA
    )
    assert body["reasoning_effort"] == provider.NVIDIA_EVIDENCE_REASONING_EFFORT == "low"
    assert body["max_tokens"] == provider.NVIDIA_EVIDENCE_MAX_OUTPUT_TOKENS == 16384
    for alternative in body["response_format"]["json_schema"]["schema"]["oneOf"]:
        selection = alternative["properties"]["supporting_signals"]
        paths = list(selection["properties"])
        assert selection["type"] == "object"
        assert selection["additionalProperties"] is False
        assert not selection.get("required")
        assert selection["maxProperties"] == 6
        expected_minimum = 0 if alternative["properties"]["abstained"]["const"] else 1
        assert selection.get("minProperties", 0) == expected_minimum
        assert all(
            value == {"type": "boolean", "const": True}
            for value in selection["properties"].values()
        )
        assert "observation" in paths
        assert "observation.queue_lag" in paths
        assert (
            "observation.db_probe_ok" in paths
        )  # Present null remains distinguishable from absence.
        assert "observation.candidate_error_rate" not in paths
        assert "samples.0.value" in paths
        for path in paths:
            finding = qualify.Finding(
                hypothesis="unknown",
                abstained=True,
                reason="Missing data.",
                supporting_signals=[path],
            )
            qualify.validate_evidence_paths(finding, facts)
    assert json.dumps(qualify.SCHEMA, sort_keys=True) == before
    other = provider.nvidia_body(
        provider.NVIDIA_MODEL, {"other": 1}, system=qualify.SYSTEM, schema=qualify.SCHEMA
    )
    assert other["response_format"]["json_schema"]["schema"]["oneOf"][0]["properties"][
        "supporting_signals"
    ]["properties"] == {"other": {"type": "boolean", "const": True}}


@pytest.mark.parametrize(
    "facts",
    [{}, {"bad.key": 1}, {str(i): i for i in range(300)}, {f"field_{i}": i for i in range(257)}],
)
def test_unaddressable_or_oversized_citation_catalog_rejected(facts):
    with pytest.raises(ValueError):
        provider.evidence_paths(facts)


def test_catalog_depth_is_bounded():
    facts = {"value": 1}
    for _ in range(10):
        facts = {"nested": facts}
    with pytest.raises(ValueError, match="nesting"):
        provider.evidence_paths(facts)


def test_wire_selection_decodes_losslessly_without_repairing_reason_or_decision():
    raw = {
        "hypothesis": "database_connectivity",
        "abstained": False,
        "action": "none",
        "reason": "The measured probe failed.",
        "supporting_signals": {"observation.db_probe_ok": True},
    }
    before = json.dumps(raw, sort_keys=True)
    decoded = provider.decode_evidence_selection(raw, {"observation.db_probe_ok", "observation"})
    assert decoded == {**raw, "supporting_signals": ["observation.db_probe_ok"]}
    assert json.dumps(raw, sort_keys=True) == before


@pytest.mark.parametrize(
    "selection",
    [
        ["a", "a"],
        {"a": 1},
        {"a": "true"},
        {"a": None},
        {"a": False},
        {"a": True, "extra": False},
    ],
)
def test_invalid_wire_selection_is_rejected_without_deduplication(selection):
    with pytest.raises(ValueError):
        provider.decode_evidence_selection({"supporting_signals": selection}, {"a"})


def test_wire_selection_still_enforces_six_citation_limit():
    selection = {f"path_{n}": True for n in range(7)}
    with pytest.raises(ValueError, match="too many"):
        provider.decode_evidence_selection({"supporting_signals": selection}, set(selection))


def test_empty_selection_is_allowed_only_when_wire_minimum_permits_it():
    raw = {"supporting_signals": {}}
    assert provider.decode_evidence_selection(raw, {"a"}, minimum=0)["supporting_signals"] == []
    with pytest.raises(ValueError, match="at least one"):
        provider.decode_evidence_selection(raw, {"a"}, minimum=1)


@pytest.mark.parametrize(
    "answer",
    [
        '{"action":"none","action":"resume_demo_worker"}',
        '{"supporting_signals":{"a":true,"a":false}}',
    ],
)
def test_duplicate_json_keys_are_rejected(answer):
    with pytest.raises(ValueError, match="duplicate JSON keys"):
        provider.model_json(answer)
