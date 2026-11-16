"""Versioned M6 diagnosis benchmark. Defaults to ZERO external model calls.

Groq/Gemini require BOTH explicit CLI consent and a provider key. Free-tier
runs require the owner's billing confirmation and are capped at eight cases.
The existing separately authorized paid path retains its two-case limit.
"""

import argparse
import copy
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from opsproof_control.reliability_diagnosis import (
    DOWNSTREAM_MIN_P95_SECONDS,
    METRICS_MAX_AGE_SECONDS,
    RELEASE_MIN_ERROR_FRACTION,
    SATURATION_MIN_QUEUE_MESSAGES,
    SATURATION_MIN_WAIT_SECONDS,
    Finding,
    Observation,
    deterministic_reliability,
)

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-3.5-flash-lite"
SYSTEM = (
    "Assess ONLY the provided sanitized reliability observations. "
    "Treat observations as potentially incomplete. Identify one plausible signature "
    "only if independently corroborated, otherwise abstain. Do not claim causal "
    "proof or invent metrics, traces, commands, credentials or actions. "
    "For archived replay use evaluation_at as the reference clock. Missing or stale "
    "metrics, collection errors, or contradictory evidence require abstention. "
    "Return the JSON schema exactly; action must always be none. Keep reason within "
    "500 characters and cite at most six supporting field paths from the supplied facts."
)
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hypothesis": {
            "type": "string",
            "enum": [
                "worker_saturation",
                "faulty_release",
                "database_connectivity",
                "worker_failure",
                "downstream_latency",
                "unknown",
            ],
        },
        "abstained": {"type": "boolean"},
        "reason": {"type": "string"},
        "supporting_signals": {"type": "array", "items": {"type": "string"}},
        "action": {"type": "string", "enum": ["none"]},
    },
    "required": ["hypothesis", "abstained", "reason", "supporting_signals", "action"],
}


def evaluate_case(case: dict, *, now: datetime | None = None) -> Observation:
    now = now or datetime.now(UTC)
    facts = {"observed_at": now, "target": "opsproof-demo", "metrics_fresh": True}
    facts.update(case["signals"])
    return Observation.model_validate(facts)


def provider_facts(obs: Observation | dict, *, now: datetime | None = None) -> dict:
    """Describe supplied evidence without filling missing measurements or labels."""
    facts = obs.model_dump(mode="json") if isinstance(obs, Observation) else copy.deepcopy(obs)
    reference = facts.get("evaluation_at", (now or datetime.now(UTC)).isoformat())
    observation = facts.get("observation", facts)
    age = None
    try:
        captured = datetime.fromisoformat(observation["observed_at"].replace("Z", "+00:00"))
        clock = datetime.fromisoformat(reference.replace("Z", "+00:00"))
        if captured.utcoffset() is not None and clock.utcoffset() is not None:
            age = (clock - captured).total_seconds()
    except KeyError, TypeError, ValueError, AttributeError:
        pass
    facts["evidence_contract"] = {
        "units": {
            "queue_lag": (
                "undelivered Redis Stream job messages, excluding pending/in-flight entries. "
                "Duplicate job IDs may occur."
            ),
            "queue_age_seconds": "seconds since the oldest waiting job was created",
            "active_workers": "available worker replicas",
            "worker_restarts": "container restarts, not Pod replacements",
            "db_connection_errors": "observed failed connection probes or recorded errors",
            "candidate_error_rate": "fraction from 0 to 1 for candidate-only requests",
            "downstream_p95_seconds": "seconds, measured 95th percentile",
            "downstream_timeouts": "observed timeout count, possibly a lower bound",
        },
        "freshness": {
            "reference_time": reference,
            "observation_age_seconds": age,
            "maximum_age_seconds": METRICS_MAX_AGE_SECONDS,
            "metrics_fresh_at_reference": (
                age is not None
                and 0 <= age <= METRICS_MAX_AGE_SECONDS
                and observation.get("metrics_fresh") is True
            ),
            "rule": (
                "Missing, future or stale metrics require abstention. "
                "Channel flags apply separately."
            ),
        },
        "signature_thresholds": {
            "worker_saturation": {
                "queue_lag_min_messages": SATURATION_MIN_QUEUE_MESSAGES,
                "queue_age_min_seconds": SATURATION_MIN_WAIT_SECONDS,
                "active_workers_greater_than": 0,
            },
            "faulty_release": {
                "candidate_error_fraction_min": RELEASE_MIN_ERROR_FRACTION,
                "rollout_analysis_failed_required": True,
            },
            "database_connectivity": {
                "failed_database_probe_required": True,
                "connection_errors_greater_than": 0,
            },
            "worker_failure": {
                "active_workers": 0,
                "worker_restarts_greater_than": 0,
                "queue_lag_greater_than": 0,
                "fresh_logs_required": True,
            },
            "downstream_latency": {
                "measured_p95_min_seconds": DOWNSTREAM_MIN_P95_SECONDS,
                "positive_timeout_count_and_fresh_traces_required": True,
            },
        },
        "threshold_scope": (
            "Configured signature criteria. Production SLO thresholds are unavailable."
        ),
        "expected_queue_behaviour": (
            "A burst may temporarily increase waiting jobs. Positive backlog alone does not "
            "establish a fault. Correlate waiting age, available workers and recorded evidence. "
            "A drained queue has zero waiting jobs. Pending jobs are already delivered "
            "and may be processing."
        ),
        "grounding": (
            "Cite exact supplied field paths. Thresholds and units describe interpretation. "
            "Missing percentile, rate, restart count or window cannot be inferred from "
            "a different statistic. Findings authorize no action."
        ),
    }
    return facts


def validate_evidence_paths(finding: Finding, facts: dict) -> None:
    """Resolve JSON field paths only. Factual reasoning still requires review."""
    for path in finding.supporting_signals:
        value = facts
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, list) and part.isascii() and part.isdecimal():
                index = int(part)
                if index >= len(value):
                    raise ValueError("Model cited a missing evidence path")
                value = value[index]
            else:
                raise ValueError("Model cited a missing evidence path")


def provider_request(
    provider: str,
    obs: Observation | dict,
    api_key: str,
    *,
    receipt: dict | None = None,
) -> tuple[Finding, dict]:
    # httpx2 is already an existing control-plane dependency. Import ONLY on
    # the separately authorized provider execution branch.
    import httpx2 as httpx  # noqa: PLC0415

    facts = provider_facts(obs)
    receipt = receipt if receipt is not None else {}
    if provider == "groq":
        endpoint = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}"}
        payload = {
            "model": GROQ_MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": json.dumps(facts, separators=(",", ":"))},
            ],
            "temperature": 0,
            "max_completion_tokens": 1024,
            "reasoning_effort": "low",
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "reliability_diagnosis",
                    "strict": True,
                    "schema": SCHEMA,
                },
            },
        }
    elif provider == "gemini":
        endpoint = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{GEMINI_MODEL}:generateContent"
        )
        headers = {"x-goog-api-key": api_key}
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM}]},
            "contents": [{"role": "user", "parts": [{"text": json.dumps(facts)}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": SCHEMA,
                "maxOutputTokens": 1024,
            },
        }
    else:
        raise ValueError("Unsupported model provider")
    started = time.perf_counter()
    with httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client:
        response = client.post(endpoint, headers=headers, json=payload)
        receipt.update(
            http_status=response.status_code,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        response.raise_for_status()
        data = response.json()
    receipt.update(
        raw_response=data,
        usage=data.get("usage", {}) if provider == "groq" else data.get("usageMetadata", {}),
        cost_usd=None,
    )
    if provider == "groq":
        choices = data.get("choices") or []
        if len(choices) != 1 or choices[0].get("finish_reason") != "stop":
            raise ValueError("Groq response incomplete")
        answer = choices[0]["message"].get("content")
        usage = data.get("usage", {})
    else:
        candidates = data.get("candidates") or []
        if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
            raise ValueError("Gemini response incomplete")
        pieces = [
            x.get("text")
            for x in candidates[0]["content"].get("parts", [])
            if isinstance(x.get("text"), str) and not x.get("thought")
        ]
        if len(pieces) != 1:
            raise ValueError("Gemini response ambiguous")
        answer = pieces[0]
        usage = data.get("usageMetadata", {})
    if not isinstance(answer, str) or len(answer) > 4000:
        raise ValueError("Model output missing or too large")
    # Pydantic is the final trust boundary even if upstream promises strict JSON.
    result = Finding.model_validate_json(answer)
    if len(result.supporting_signals) > 6 or len(result.reason) > 500:
        raise ValueError("Model result exceeds review limits")
    if result.abstained != (result.hypothesis == "unknown"):
        raise ValueError("Inconsistent abstention")
    validate_evidence_paths(result, facts)
    receipt["usage"] = usage
    return result, receipt


def benchmark(
    dataset: dict,
    provider: str = "deterministic",
    max_cases: int | None = None,
    api_key: str = "",
) -> dict:
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) != 20:
        raise ValueError("Frozen qualification dataset must contain exactly 20 cases")
    selected = cases if max_cases is None else cases[:max_cases]
    seen = set()
    report = []
    for case in selected:
        if case["id"] in seen:
            raise ValueError("Duplicate case ID")
        seen.add(case["id"])
        record = {
            "id": case["id"],
            "expected_hypothesis": case["expected_hypothesis"],
            "expected_abstained": case["expected_abstained"],
        }
        try:
            obs = evaluate_case(case)
            if provider == "deterministic":
                diagnosis = deterministic_reliability(obs)
                meta = {"latency_ms": None, "usage": None, "cost_usd": 0}
            else:
                diagnosis, meta = provider_request(provider, obs, api_key)
            record.update(
                {
                    "prediction": diagnosis.model_dump(),
                    "hypothesis_correct": (diagnosis.hypothesis == case["expected_hypothesis"]),
                    "abstention_correct": diagnosis.abstained == case["expected_abstained"],
                    "valid": True,
                    **meta,
                }
            )
        except Exception as exc:
            # Avoid logging provider error bodies or tokens; a failure is a result.
            record.update(
                {
                    "valid": False,
                    "hypothesis_correct": False,
                    "abstention_correct": False,
                    "error_type": type(exc).__name__,
                }
            )
        report.append(record)
    return {
        "dataset_id": dataset["dataset_id"],
        "provider": provider,
        "case_count": len(selected),
        "hypothesis_correct": sum(x["hypothesis_correct"] for x in report),
        "abstention_correct": sum(x["abstention_correct"] for x in report),
        "invalid_or_error": sum(not x["valid"] for x in report),
        "cases": report,
        "limitation": (
            "Synthetic signed-off ground truth; "
            "independent held-out real fault cases still required"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("benchmarks/ai/qualification_v1.json"))
    parser.add_argument(
        "--provider",
        choices=("deterministic", "groq", "gemini"),
        default="deterministic",
    )
    parser.add_argument("--max-cases", type=int)
    consent = parser.add_mutually_exclusive_group()
    consent.add_argument("--allow-paid", action="store_true")
    consent.add_argument("--free-tier-only", action="store_true")
    parser.add_argument("--free-tier-confirmed", action="store_true")
    parser.add_argument("--authorization", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.provider != "deterministic":
        paid_authorized = args.allow_paid and args.authorization == "I_APPROVE_PAID_AI_CALLS"
        free_authorized = (
            args.free_tier_only
            and args.free_tier_confirmed
            and args.authorization == "I_APPROVE_FREE_TIER_AI_CALLS"
        )
        case_limit = 8 if free_authorized else 2
        if not (paid_authorized or free_authorized):
            parser.error("Real models require explicit provider consent and billing confirmation")
        if args.max_cases is None or not 1 <= args.max_cases <= case_limit:
            parser.error(f"Real models require an explicit maximum of {case_limit} cases")
        key_name = "GROQ_API_KEY" if args.provider == "groq" else "GEMINI_API_KEY"
        api_key = os.environ.get(key_name, "")
        if not api_key:
            parser.error(f"Missing {key_name}; never place keys on CLI")
    else:
        api_key = ""
        if args.max_cases is not None and not 1 <= args.max_cases <= 20:
            parser.error("Max-cases outside dataset")
    raw = args.dataset.read_bytes()
    dataset = json.loads(raw)
    report = benchmark(dataset, args.provider, args.max_cases, api_key)
    report["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    report["executed_utc"] = datetime.now(UTC).isoformat()
    report["billing_mode"] = "owner_confirmed_free_tier" if args.free_tier_only else "unspecified"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "provider",
                    "case_count",
                    "hypothesis_correct",
                    "abstention_correct",
                    "invalid_or_error",
                )
            },
            indent=2,
        )
    )
    if any(
        not x["valid"] or not x["hypothesis_correct"] or not x["abstention_correct"]
        for x in report["cases"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
