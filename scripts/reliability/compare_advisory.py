"""Execute an explicitly approved frozen 8+4 advisory comparison, at most 24 calls.

No runtime AI enablement, provider fallback or automatic retry. Dispatch records
are written before requests; an interrupted run cannot be silently restarted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from scripts.platform.render_local_secrets import read_env
from scripts.reliability import qualify

ROOT = Path(__file__).resolve().parents[2]
MAX_REQUESTS = 24


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inputs(directory: Path) -> tuple[dict, list[dict], dict]:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if (
        manifest.get("request_ceiling") != MAX_REQUESTS
        or manifest.get("cases") != 12
        or manifest.get("automatic_retries") != 0
        or manifest.get("fallbacks") != 0
        or manifest.get("models") != {"groq": qualify.GROQ_MODEL, "gemini": qualify.GEMINI_MODEL}
    ):
        raise ValueError("Frozen comparison bounds or model identities differ")
    for file, key in (
        ("requests.json", "request_file_sha256"),
        ("labels-private.json", "labels_file_sha256"),
    ):
        if digest(directory / file) != manifest.get(key):
            raise ValueError("Frozen comparison input integrity mismatch")
    if digest(ROOT / "scripts/reliability/qualify.py") != manifest.get("provider_code_sha256"):
        raise ValueError("Provider implementation differs from frozen review")
    if hashlib.sha256(qualify.SYSTEM.encode()).hexdigest() != manifest.get("prompt_sha256"):
        raise ValueError("Frozen prompt differs")
    if hashlib.sha256(
        json.dumps(qualify.SCHEMA, sort_keys=True).encode()
    ).hexdigest() != manifest.get("schema_sha256"):
        raise ValueError("Frozen output schema differs")
    cases = json.loads((directory / "requests.json").read_text(encoding="utf-8"))["cases"]
    labels = json.loads((directory / "labels-private.json").read_text(encoding="utf-8"))["cases"]
    ids = [case["id"] for case in cases]
    if len(cases) != 12 or len(set(ids)) != 12 or len(labels) != 12:
        raise ValueError("Exactly twelve uniquely identified cases and labels required")
    if {row["id"] for row in labels} != set(ids):
        raise ValueError("Labels differ from comparison cases")
    if {
        split: sum(case["split"] == split for case in cases) for split in ("regression", "held_out")
    } != {"regression": 8, "held_out": 4}:
        raise ValueError("Regression and held-out splits differ")
    for case in cases:
        if qualify.provider_facts(case["facts"]) != case["facts"]:
            raise ValueError("Request facts are not the identical frozen evidence contract")
        if len(json.dumps(case["facts"]).encode()) > 4096:
            raise ValueError("Case input exceeds approved size")
    return manifest, cases, {row["id"]: row for row in labels}


def write(path: Path, value: dict, *, exclusive=False) -> None:
    with path.open("x" if exclusive else "w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def execute(directory: Path, approved_hash: str, keys: dict[str, str]) -> dict:
    manifest, cases, labels = inputs(directory)
    if approved_hash != manifest["request_file_sha256"]:
        raise ValueError("Approval must bind the exact frozen request file")
    if set(keys) != {"groq", "gemini"} or not keys.get("groq") or not keys.get("gemini"):
        raise ValueError("Both provider keys required before starting; no calls issued")
    write(
        directory / "execution-started.json",
        {
            "started_at": datetime.now(UTC).isoformat(),
            "request_ceiling": MAX_REQUESTS,
            "approved_request_sha256": approved_hash,
            "owner_confirmed_free_no_paid_billing": True,
            "automatic_retries": 0,
            "fallbacks": 0,
        },
        exclusive=True,
    )
    calls = directory / "calls"
    calls.mkdir(exist_ok=False)
    result = {
        "finished": False,
        "external_requests_issued": 0,
        "runtime_ai_enabled": False,
        "request_ceiling": MAX_REQUESTS,
        "providers": {name: [] for name in keys},
        "stopped_providers": {},
        "independent_factual_review": "PENDING",
        "expected_cost_usd": 0,
        "invoice_verified": False,
    }
    started = time.monotonic()
    try:
        for case in cases:
            round_started = time.monotonic()
            for provider in ("groq", "gemini"):
                if provider in result["stopped_providers"]:
                    continue
                if (
                    result["external_requests_issued"] >= MAX_REQUESTS
                    or time.monotonic() - started > 900
                ):
                    raise RuntimeError("Approved comparison bound reached")
                number = result["external_requests_issued"] + 1
                path = calls / f"{number:02d}-{provider}.json"
                row = {
                    "id": case["id"],
                    "split": case["split"],
                    "provider": provider,
                    "issued_at": datetime.now(UTC).isoformat(),
                    "request_number": number,
                    "status": "ISSUED_OUTCOME_UNKNOWN",
                }
                write(path, row, exclusive=True)
                result["external_requests_issued"] = number
                receipt = {}
                try:
                    prediction, receipt = qualify.provider_request(
                        provider, case["facts"], keys[provider], receipt=receipt
                    )
                    expected = labels[case["id"]]
                    correct = (
                        prediction.hypothesis == expected["expected_hypothesis"]
                        and prediction.abstained == expected["expected_abstained"]
                    )
                    row.update(
                        status="RETURNED_VALID",
                        prediction=prediction.model_dump(),
                        hypothesis_and_abstention_correct=correct,
                    )
                except Exception as exc:
                    row.update(
                        status="FAILED_OR_INVALID",
                        error_type=type(exc).__name__,
                        hypothesis_and_abstention_correct=False,
                    )
                    # Avoid repeated HTTP/auth/quota failures or unknown timeout outcomes.
                    if "http_status" not in receipt or receipt["http_status"] != 200:
                        result["stopped_providers"][provider] = {
                            "error_type": type(exc).__name__,
                            "http_status": receipt.get("http_status"),
                        }
                row["receipt"] = receipt
                write(path, row)
                result["providers"][provider].append(row)
                write(directory / "execution-result.json", result)
                print(f"{number}/24 {provider} {case['split']} {row['status']}", flush=True)
            if case is not cases[-1] and len(result["stopped_providers"]) < 2:
                # Three requests per provider/minute avoids unnecessary quota collisions.
                time.sleep(max(0, 20 - (time.monotonic() - round_started)))
        result["finished"] = True
    finally:
        result["finished_at"] = datetime.now(UTC).isoformat()
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        result["scores"] = {
            provider: {
                split: {
                    "issued": sum(row["split"] == split for row in rows),
                    "correct": sum(
                        row["split"] == split and row["hypothesis_and_abstention_correct"]
                        for row in rows
                    ),
                }
                for split in ("regression", "held_out")
            }
            for provider, rows in result["providers"].items()
        }
        result["status"] = "COMPARISON_RECORDED_REVIEW_PENDING_AI_DISABLED"
        write(directory / "execution-result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--confirm-free-tier-no-paid-billing", action="store_true")
    parser.add_argument("--approved-request-sha256")
    args = parser.parse_args()
    manifest, cases, _labels = inputs(args.inputs)
    if not args.execute:
        print(
            json.dumps(
                {
                    "status": "FROZEN_INPUTS_VERIFIED_ZERO_CALLS",
                    "cases": len(cases),
                    "request_ceiling": MAX_REQUESTS,
                    "request_sha256": manifest["request_file_sha256"],
                }
            )
        )
        return 0
    if not args.confirm_free_tier_no_paid_billing or not args.approved_request_sha256:
        parser.error("Explicit free-tier confirmation and approved request hash required")
    configured = read_env(ROOT / ".env")
    keys = {
        provider: os.environ.get(name) or configured.get(name, "")
        for provider, name in (("groq", "GROQ_API_KEY"), ("gemini", "GEMINI_API_KEY"))
    }
    result = execute(args.inputs, args.approved_request_sha256, keys)
    print(
        json.dumps(
            {
                key: result[key]
                for key in ("status", "external_requests_issued", "scores", "stopped_providers")
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
