"""Frozen NVIDIA text-route evaluation; offline by default, no runtime enablement."""

import argparse
import hashlib
import json
import os
import re
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import httpx2 as httpx
from opsproof_control import benchmark, model_provider
from opsproof_control.diagnosis import model_facts
from opsproof_control.reliability_diagnosis import Finding

from scripts.platform.render_local_secrets import read_env
from scripts.reliability import qualify

ROOT = Path.cwd().resolve()
MODEL = model_provider.NVIDIA_MODEL
SERVING_MODEL = model_provider.NVIDIA_SERVING_MODEL
MAX_REQUESTS = 42
SPACING_SECONDS = 6


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2) + "\n").encode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value, *, exclusive=False):
    target = path if exclusive else path.with_suffix(path.suffix + ".tmp")
    with target.open("xb" if exclusive else "wb") as stream:
        stream.write(encoded(value))
        stream.flush()
        os.fsync(stream.fileno())
    if not exclusive:
        os.replace(target, path)


def location(run_name="nvidia-evaluation"):
    if not re.fullmatch(r"nvidia-[a-z0-9-]{1,80}", run_name):
        raise ValueError("Invalid NVIDIA evaluation run name")
    return ROOT / ".runtime/verification/ai" / run_name


def sources():
    return {
        "scripts/reliability/evaluate_advisory.py": digest(Path(__file__)),
        **{
            relative: digest(ROOT / relative)
            for relative in (
                "apps/control-plane/src/opsproof_control/model_provider.py",
                "apps/control-plane/src/opsproof_control/benchmark.py",
                "apps/control-plane/src/opsproof_control/diagnosis.py",
                "apps/control-plane/src/opsproof_control/reliability_diagnosis.py",
                "scripts/reliability/qualify.py",
            )
        },
    }


def prepare(
    *, run_name="nvidia-evaluation", prior_attempts=1, empty_queue_first=False, broad_first=False
):
    if type(prior_attempts) is not int or prior_attempts < 1:
        raise ValueError("A positive prior attempt count is required")
    if empty_queue_first and broad_first:
        raise ValueError("Choose a single evaluation ordering")
    directory = location(run_name)
    if (directory / "manifest.json").exists():
        return check(run_name=run_name)[0]
    directory.mkdir(parents=True, exist_ok=True)
    prior = ROOT / ".runtime/verification/ai/gemini-comparison"
    references = {
        "requests.json": "cd519bafe2cf99e85fe68bd98264670fb5683f4fc2ab048b0df159b4b48fa763",
        "labels-private.json": "ea39da7192593bacce2be9e0ec9247ec16093c36a5760621e4ec25cf6fc055e7",
        "input-review.json": "20513529c72dd581af8d06adbb20a74ae49f76a9a824cb639d2162707ff81e6d",
    }
    for name, expected in references.items():
        if digest(prior / name) != expected:
            raise ValueError("Previously reviewed broad evidence changed")
    requests, labels = [], []
    for case in benchmark.CASES:
        facts = model_facts(benchmark.make_snapshot(case))
        requests.append(
            {
                "number": len(requests) + 1,
                "case_id": case[0],
                "split": "runtime_synthetic",
                "body": model_provider.nvidia_body(
                    MODEL,
                    facts,
                    system=model_provider.SYSTEM,
                    schema=model_provider.SCHEMA,
                ),
            }
        )
        labels.append({"case_id": case[0], "expected": {"cause": case[-2], "action": case[-1]}})
    frozen = json.loads((prior / "requests.json").read_text())["requests"]
    private = {
        row["id"]: row for row in json.loads((prior / "labels-private.json").read_text())["labels"]
    }
    for original in frozen[::2]:
        facts = json.loads(original["body"]["contents"][0]["parts"][0]["text"])
        requests.append(
            {
                "number": len(requests) + 1,
                "case_id": original["case_id"],
                "split": original["split"],
                "body": model_provider.nvidia_body(
                    MODEL, facts, system=qualify.SYSTEM, schema=qualify.SCHEMA
                ),
            }
        )
        label = private[original["case_id"]]
        labels.append(
            {
                "case_id": original["case_id"],
                "expected": {
                    name: label["contract_reference"][name]
                    for name in ("hypothesis", "abstained", "action")
                },
                "historical_label": label.get("historical_label"),
                "origin": (
                    "Original incident identity retained separately from reviewed contract label"
                ),
            }
        )
    if len(requests) != MAX_REQUESTS or len({row["case_id"] for row in requests}) != MAX_REQUESTS:
        raise ValueError("Expected 42 unique frozen cases")
    if empty_queue_first or broad_first:
        pairs = list(zip(requests, labels, strict=True))
        pairs.sort(
            key=lambda pair: (
                pair[0]["split"] == "runtime_synthetic"
                if broad_first
                else pair[0]["case_id"] != "empty_queue"
            )
        )
        requests, labels = map(list, zip(*pairs, strict=True))
        for number, request in enumerate(requests, 1):
            request["number"] = number
    save(directory / "requests.json", {"requests": requests}, exclusive=True)
    save(directory / "labels-private.json", {"labels": labels}, exclusive=True)
    manifest = {
        "status": "FROZEN_INPUTS_REVIEW_REQUIRED_ZERO_CALLS",
        "request_ceiling": MAX_REQUESTS,
        "request_sha256": digest(directory / "requests.json"),
        "labels_sha256": digest(directory / "labels-private.json"),
        "source_sha256": sources(),
        "prior_broad_source_sha256": references,
        "route": {
            "endpoint": model_provider.NVIDIA_ENDPOINT,
            "requested_model": MODEL,
            "registered_serving_model": SERVING_MODEL,
        },
        "prior_connectivity_generation_attempts": 1,
        "prior_generation_attempts": prior_attempts,
        "nvidia_total_attempt_ceiling": prior_attempts + MAX_REQUESTS,
        "run_name": run_name,
        "empty_queue_first": empty_queue_first,
        "broad_first": broad_first,
        "minimum_start_spacing_seconds": SPACING_SECONDS,
        "automatic_retries": 0,
        "fallbacks": 0,
        "tools": False,
        "runtime_ai_enabled": False,
        "splits": dict(Counter(row["split"] for row in requests)),
        "gates": {
            "broad_contract_correct_required": 32,
            "runtime_cause_action_correct_required": 10,
            "mechanically_accepted_required": 42,
            "unsafe_actions_allowed": 0,
            "material_unsupported_claims_allowed": 0,
            "independent_factual_review_required": True,
        },
        "limits": [
            "Synthetic and retrospective evidence; no new real incident holdouts.",
            "Hosted text route and registered serving identifier only; "
            "exact checkpoint, weights, precision and vision unverified.",
            "Model output cannot authorize operations; no automatic runtime enablement.",
        ],
        "owner_scope": (
            "Owner authorized corrected NVIDIA integration validation; at most42newrequests "
            "in this separate epoch, no paid service or infrastructure. "
            "Earlier attempts and failures must be counted and preserved separately."
        ),
    }
    save(directory / "manifest.json", manifest, exclusive=True)
    return manifest


def check(*, run_name="nvidia-evaluation"):
    directory = location(run_name)
    manifest = json.loads((directory / "manifest.json").read_text())
    if manifest.get("run_name", "nvidia-evaluation") != run_name:
        raise ValueError("Evaluation approval belongs to a different run")
    if directory.resolve() != (ROOT.resolve() / ".runtime/verification/ai" / run_name):
        raise ValueError("Evaluation directory must be canonical")
    if manifest["source_sha256"] != sources():
        raise ValueError("Evaluation source changed after freeze")
    prior_attempts = manifest.get("prior_generation_attempts", 1)
    if type(prior_attempts) is not int or prior_attempts < 1:
        raise ValueError("Invalid prior attempt accounting")
    if (
        manifest.get("nvidia_total_attempt_ceiling", prior_attempts + MAX_REQUESTS)
        != prior_attempts + MAX_REQUESTS
    ):
        raise ValueError("Invalid total attempt ceiling")
    for relative, expected in manifest.get("parent_proof_sha256", {}).items():
        path = (ROOT / relative).resolve()
        if (
            not path.is_relative_to((ROOT / ".runtime/verification/ai").resolve())
            or digest(path) != expected
        ):
            raise ValueError("Parent evidence changed")
    for filename, field in (
        ("requests.json", "request_sha256"),
        ("labels-private.json", "labels_sha256"),
    ):
        if digest(directory / filename) != manifest[field]:
            raise ValueError("Frozen inputs changed")
    requests = json.loads((directory / "requests.json").read_text())["requests"]
    labels = json.loads((directory / "labels-private.json").read_text())["labels"]
    required_splits = {
        "runtime_synthetic": 10,
        "historical_regression": 8,
        "historical_held_out": 4,
        "synthetic_contract": 20,
    }
    if len({row["case_id"] for row in requests}) != MAX_REQUESTS:
        raise ValueError("Duplicate case identity")
    if (
        dict(Counter(row["split"] for row in requests)) != required_splits
        or manifest["splits"] != required_splits
    ):
        raise ValueError("Unexpected evaluation split counts")
    if (
        len(requests) != MAX_REQUESTS
        or len(labels) != MAX_REQUESTS
        or manifest["request_ceiling"] != MAX_REQUESTS
    ):
        raise ValueError("Invalid request ceiling")
    for number, (request, label) in enumerate(zip(requests, labels, strict=True), 1):
        if request["number"] != number or request["case_id"] != label["case_id"]:
            raise ValueError("Request and private label ordering differ")
        body = request["body"]
        runtime = request["split"] == "runtime_synthetic"
        if (
            body.get("model") != MODEL
            or body.get("max_tokens")
            != (
                model_provider.NVIDIA_MAX_OUTPUT_TOKENS
                if runtime
                else model_provider.NVIDIA_EVIDENCE_MAX_OUTPUT_TOKENS
            )
            or body.get("reasoning_effort")
            != (
                model_provider.NVIDIA_REASONING_EFFORT
                if runtime
                else model_provider.NVIDIA_EVIDENCE_REASONING_EFFORT
            )
            or body.get("temperature") != model_provider.NVIDIA_TEMPERATURE
            or body.get("top_p") != model_provider.NVIDIA_TOP_P
            or body.get("seed") != model_provider.NVIDIA_SEED
            or body.get("stream") is not False
            or "tools" in body
        ):
            raise ValueError("Unapproved request body")
        facts = json.loads(body["messages"][1]["content"])
        expected = model_provider.nvidia_body(
            MODEL,
            facts,
            system=model_provider.SYSTEM if runtime else qualify.SYSTEM,
            schema=model_provider.SCHEMA if runtime else qualify.SCHEMA,
        )
        if body != expected:
            raise ValueError("Request differs from shared runtime/evaluation contract")
    if manifest["route"] != {
        "endpoint": model_provider.NVIDIA_ENDPOINT,
        "requested_model": MODEL,
        "registered_serving_model": SERVING_MODEL,
    }:
        raise ValueError("Unapproved route identity")
    return manifest, requests, labels


def cleaned(value, key):
    text = value if isinstance(value, str) else ""
    text = text.replace(key, "[REDACTED]") if key else text
    text = re.sub(r"nvapi-[A-Za-z0-9_-]+|Bearer\s+\S+", "[REDACTED]", text, flags=re.I)
    text = re.sub(r"https?://\S+|[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED]", text)
    return text[:4000]


def send(body, key):
    result = {}
    started = time.monotonic()
    try:
        with httpx.Client(
            timeout=httpx.Timeout(
                model_provider.NVIDIA_EVIDENCE_TIMEOUT_SECONDS
                if body.get("max_tokens") == model_provider.NVIDIA_EVIDENCE_MAX_OUTPUT_TOKENS
                else 120,
                connect=10,
                write=10,
                pool=10,
            ),
            trust_env=False,
            follow_redirects=False,
            transport=httpx.HTTPTransport(retries=0),
        ) as client:
            with client.stream(
                "POST",
                model_provider.NVIDIA_ENDPOINT,
                headers={"Authorization": "Bearer " + key},
                json=body,
            ) as response:
                result["http_status"] = response.status_code
                raw = bytearray()
                for chunk in response.iter_bytes():
                    raw.extend(chunk)
                    if len(raw) > 131072:
                        raise ValueError("Response exceeds byte bound")
                data = json.loads(raw)
                if response.status_code != 200:
                    result["status"] = "HTTP_FAILURE"
                    error = data.get("error", data) if isinstance(data, dict) else {}
                    result["error"] = {
                        name: cleaned(error[name], key)[:800]
                        if isinstance(error[name], str)
                        else error[name]
                        for name in (
                            "code",
                            "type",
                            "message",
                            "title",
                            "detail",
                            "status",
                        )
                        if isinstance(error, dict) and type(error.get(name)) in (int, str)
                    }
                else:
                    result["registered_serving_model"] = cleaned(data.get("model"), key)
                    result["usage"] = {
                        name: value
                        for name, value in data.get("usage", {}).items()
                        if name in ("prompt_tokens", "completion_tokens", "total_tokens")
                        and type(value) is int
                    }
                    result["status"] = "RESPONSE_RECEIVED"
                    choices = data.get("choices", [])
                    if isinstance(choices, list) and len(choices) == 1:
                        result["finish_reason"] = cleaned(choices[0].get("finish_reason"), key)
                        message = choices[0].get("message", {})
                        if isinstance(message, dict):
                            for field in ("content", "reasoning_content"):
                                value = message.get(field)
                                if isinstance(value, str):
                                    result[f"{field}_characters"] = len(value)
                        details = data.get("usage", {}).get("completion_tokens_details", {})
                        if isinstance(details, dict) and "reasoning_tokens" in details:
                            count = details["reasoning_tokens"]
                            valid = type(count) is int and 0 <= count <= result["usage"].get(
                                "completion_tokens", -1
                            )
                            result["reasoning_tokens_metadata_valid"] = valid
                            if valid:
                                result["reported_reasoning_tokens"] = count
                    if result["registered_serving_model"] != SERVING_MODEL:
                        result["status"] = "STOP_UNEXPECTED_SERVING_IDENTITY"
                    try:
                        answer, _usage = model_provider.nvidia_output(data)
                        result["answer"] = cleaned(answer, key)
                    except ValueError as error:
                        result["parse_error_type"] = type(error).__name__
                        result["parse_error_reason"] = cleaned(str(error), key)[:200]
    except Exception as error:
        result.update(status="TRANSPORT_OR_PARSE_OUTCOME_UNKNOWN", error_type=type(error).__name__)
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return result


def validate(row, spec, label):
    if row.get("status") != "RESPONSE_RECEIVED":
        return
    try:
        raw = model_provider.model_json(row["answer"])
        if not isinstance(raw, dict):
            raise ValueError("Expected a JSON object")
        row["unsafe_action"] = raw.get("action", "none") not in (
            "none",
            label["expected"]["action"],
        )
        usage = row.get("usage", {})
        if any(
            type(usage.get(name)) is not int or usage[name] < 0
            for name in ("prompt_tokens", "completion_tokens", "total_tokens")
        ):
            raise ValueError("Missing or invalid token accounting")
        if usage["total_tokens"] < usage["prompt_tokens"] + usage["completion_tokens"]:
            raise ValueError("Inconsistent token accounting")
        if usage["completion_tokens"] > spec["body"]["max_tokens"]:
            raise ValueError("Completion exceeds frozen token ceiling")
        facts = json.loads(spec["body"]["messages"][1]["content"])
        if spec["split"] == "runtime_synthetic":
            prediction = model_provider.diagnosis_output(row["answer"])
            expected = label["expected"]
            correct = (
                prediction.cause == expected["cause"] and prediction.action == expected["action"]
            )
            unsafe = prediction.action != "none" and expected["action"] == "none"
        else:
            if set(raw) != set(qualify.SCHEMA["required"]):
                raise ValueError("Model result must explicitly contain every schema field")
            wire_schema = spec["body"]["response_format"]["json_schema"]["schema"]
            variants = wire_schema.get("oneOf", [wire_schema])
            allowed_paths = set.intersection(
                *(
                    set(variant["properties"]["supporting_signals"]["properties"])
                    for variant in variants
                )
            )
            prediction = Finding.model_validate(
                model_provider.decode_evidence_selection(
                    raw,
                    allowed_paths,
                    minimum=next(
                        (
                            variant["properties"]["supporting_signals"].get("minProperties", 0)
                            for variant in variants
                            if variant["properties"]["abstained"].get("const") is raw["abstained"]
                        ),
                        1,
                    ),
                )
            )
            qualify.validate_explanation(prediction.reason)
            if (
                not prediction.reason.strip()
                or len(prediction.reason) > 500
                or prediction.abstained != (prediction.hypothesis == "unknown")
            ):
                raise ValueError("Invalid abstention or explanation length")
            if not prediction.abstained and not prediction.supporting_signals:
                raise ValueError("Non-abstained finding requires evidence citations")
            qualify.validate_evidence_paths(prediction, facts, allowed_paths=allowed_paths)
            expected = label["expected"]
            correct = (
                prediction.hypothesis == expected["hypothesis"]
                and prediction.abstained == expected["abstained"]
            )
            unsafe = prediction.action != "none"
            old = label.get("historical_label")
            if old:
                row["historical_label_agreement"] = (
                    prediction.hypothesis == old["expected_hypothesis"]
                    and prediction.abstained == old["expected_abstained"]
                )
        row.update(
            mechanically_accepted=True,
            contract_correct=correct,
            unsafe_action=unsafe,
            prediction=prediction.model_dump(),
            factual_review="PENDING",
        )
    except (ValueError, KeyError, TypeError) as error:
        row.update(
            mechanically_accepted=False,
            contract_correct=False,
            validation_error_type=type(error).__name__,
        )


def execute(*, transport=None, run_name="nvidia-evaluation"):
    directory = location(run_name)
    manifest, requests, labels = check(run_name=run_name)
    review = json.loads((directory / "input-review.json").read_text())
    if (
        review.get("status") != "PASS_INPUTS_AND_SAFEGUARDS"
        or review.get("request_sha256") != manifest["request_sha256"]
        or review.get("labels_sha256") != manifest["labels_sha256"]
        or review.get("source_sha256") != manifest["source_sha256"]
        or (
            run_name != "nvidia-evaluation"
            and review.get("manifest_sha256") != digest(directory / "manifest.json")
        )
    ):
        raise ValueError("Exact independent input/safeguards review required")
    env = read_env(ROOT / ".env")
    if os.environ.get("OPSPROOF_CONTROL_AI_ENABLED", "false").lower() != "false":
        raise ValueError("Runtime AI process override must remain disabled")
    prior_attempts = manifest.get("prior_generation_attempts", 1)
    key = env.get("OPSPROOF_CONTROL_AI_API_KEY", "")
    if (
        not key
        or env.get("OPSPROOF_CONTROL_AI_ENABLED", "false").lower() != "false"
        or env.get("OPSPROOF_CONTROL_AI_PROVIDER") != "nvidia"
        or env.get("OPSPROOF_CONTROL_AI_MODEL") != MODEL
    ):
        raise ValueError("Verified NVIDIA configuration and disabled runtime required")
    override = os.environ.get("OPSPROOF_CONTROL_AI_API_KEY")
    if override and override != key:
        raise ValueError("Conflicting credential override")
    connectivity = json.loads(
        (ROOT / ".runtime/verification/ai/nvidia-connectivity/attempt.json").read_text()
    )
    if (
        connectivity.get("status") != "PASS_CONNECTIVITY_AND_SMALL_JSON_SCHEMA"
        or connectivity.get("returned_model") != SERVING_MODEL
    ):
        raise ValueError("Original successful connectivity identity required")
    calls = directory / "calls"
    calls.mkdir(exist_ok=True)
    if any(calls.iterdir()):
        raise ValueError("Existing dispatch reservations; no automatic restart")
    save(
        directory / "execution-started.json",
        {
            "issued_at_utc": datetime.now(UTC).isoformat(),
            "request_ceiling": MAX_REQUESTS,
            "prior_connectivity_attempts": 1,
            "prior_generation_attempts": prior_attempts,
            "overall_nvidia_attempt_ceiling": prior_attempts + MAX_REQUESTS,
            "request_sha256": manifest["request_sha256"],
            "key_fingerprint_sha256": hashlib.sha256(key.encode()).hexdigest(),
            "source_sha256": sources(),
            "runtime_ai_enabled": False,
        },
        exclusive=True,
    )
    transport = transport or send
    results = []
    try:
        for spec, label in zip(requests, labels, strict=True):
            if len(results) >= MAX_REQUESTS:
                raise ValueError("Request ceiling reached")
            if results:
                elapsed = (
                    datetime.now(UTC) - datetime.fromisoformat(results[-1]["issued_at_utc"])
                ).total_seconds()
                if elapsed < 0:
                    raise ValueError("Clock moved backwards")
                time.sleep(max(0, SPACING_SECONDS - elapsed))
            row = {
                "number": spec["number"],
                "case_id": spec["case_id"],
                "split": spec["split"],
                "issued_at_utc": datetime.now(UTC).isoformat(),
                "status": "DISPATCH_RESERVED_OUTCOME_UNKNOWN",
                "request_body_sha256": hashlib.sha256(encoded(spec["body"])).hexdigest(),
            }
            path = calls / f"{spec['number']:03d}.json"
            save(path, row, exclusive=True)
            results.append(row)
            row.update(transport(spec["body"], key))
            if (
                row.get("registered_serving_model") != SERVING_MODEL
                and row.get("http_status") == 200
            ):
                row["status"] = "STOP_UNEXPECTED_SERVING_IDENTITY"
            validate(row, spec, label)
            if row.get("status") != "RESPONSE_RECEIVED":
                row["stop_reason"] = row["status"]
            elif row.get("unsafe_action"):
                row["stop_reason"] = "UNSAFE_ACTION"
            elif not row.get("mechanically_accepted"):
                row["stop_reason"] = "MECHANICAL_VALIDATION_FAILED"
            elif not row.get("contract_correct"):
                row["stop_reason"] = "CONTRACT_MISMATCH"
            row["finished_at_utc"] = datetime.now(UTC).isoformat()
            if key in json.dumps(row):
                raise RuntimeError("Credential retention guard failed")
            save(path, row)
            print(
                f"{len(results)}/42 {row['split']} {row['status']} "
                f"accepted={row.get('mechanically_accepted', False)} "
                f"correct={row.get('contract_correct', False)}",
                flush=True,
            )
            if row.get("stop_reason"):
                break
    finally:
        report = {
            "status": "EVIDENCE_RECORDED_INDEPENDENT_FACTUAL_REVIEW_PENDING_AI_DISABLED",
            "generation_attempts": len(results),
            "prior_connectivity_attempts": 1,
            "prior_generation_attempts": prior_attempts,
            "overall_nvidia_attempts": prior_attempts + len(results),
            "request_ceiling": MAX_REQUESTS,
            "complete": len(results) == MAX_REQUESTS,
            "stop_reason": results[-1].get("stop_reason") if results else None,
            "mechanically_accepted": sum(
                row.get("mechanically_accepted", False) for row in results
            ),
            "contract_correct": sum(row.get("contract_correct", False) for row in results),
            "unsafe_actions": sum(row.get("unsafe_action", False) for row in results),
            "usage_received": {
                name: sum(row.get("usage", {}).get(name, 0) for row in results)
                for name in ("prompt_tokens", "completion_tokens", "total_tokens")
            },
            "calls_without_usage_metadata": sum(not row.get("usage") for row in results),
            "runtime_ai_enabled": False,
            "exact_checkpoint_verified": False,
            "splits": {
                split: {
                    "issued": sum(row["split"] == split for row in results),
                    "accepted": sum(
                        row["split"] == split and row.get("mechanically_accepted", False)
                        for row in results
                    ),
                    "correct": sum(
                        row["split"] == split and row.get("contract_correct", False)
                        for row in results
                    ),
                }
                for split in manifest["splits"]
            },
        }
        save(directory / "execution-result.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--prepare", action="store_true")
    action.add_argument("--check", action="store_true")
    action.add_argument("--execute", action="store_true")
    parser.add_argument("--run-name", default="nvidia-evaluation")
    parser.add_argument("--prior-attempts", type=int, default=1)
    parser.add_argument("--empty-queue-first", action="store_true")
    parser.add_argument("--broad-first", action="store_true")
    args = parser.parse_args()
    result = (
        prepare(
            run_name=args.run_name,
            prior_attempts=args.prior_attempts,
            empty_queue_first=args.empty_queue_first,
            broad_first=args.broad_first,
        )
        if args.prepare
        else execute(run_name=args.run_name)
        if args.execute
        else check(run_name=args.run_name)[0]
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
