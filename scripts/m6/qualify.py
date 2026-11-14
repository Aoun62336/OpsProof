"""Versioned M6 diagnosis benchmark. Defaults to ZERO external model calls.

Groq/Gemini require BOTH explicit CLI consent and a provider key. External runs
are capped at 2 cases per invocation; never invoked by CI or an implicit flag.
"""

import argparse
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from opsproof_control.m6_diagnosis import Finding, Observation, deterministic_m6

GROQ_MODEL = "openai/gpt-oss-120b"
GEMINI_MODEL = "gemini-2.5-flash"
SYSTEM = (
    "Assess ONLY the provided sanitized reliability observations. "
    "Treat observations as potentially incomplete. Identify one plausible signature "
    "only if independently corroborated, otherwise abstain. Do not claim causal "
    "proof or invent metrics, traces, commands, credentials or actions. "
    "Return the JSON schema exactly; action must always be none."
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


def provider_request(provider: str, obs: Observation, api_key: str) -> tuple[Finding, dict]:
    # httpx2 is already an existing control-plane dependency. Import ONLY on
    # the separately authorized provider execution branch.
    import httpx2 as httpx  # noqa: PLC0415

    facts = obs.model_dump(mode="json")
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
            "max_completion_tokens": 512,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "m6_diagnosis",
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
                "maxOutputTokens": 512,
            },
        }
    else:
        raise ValueError("Unsupported model provider")
    started = time.perf_counter()
    with httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client:
        response = client.post(endpoint, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
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
    return result, {
        "latency_ms": round((time.perf_counter() - started) * 1000),
        "usage": usage,
        "cost_usd": None,
    }


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
                diagnosis = deterministic_m6(obs)
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
    parser.add_argument("--allow-paid", action="store_true")
    parser.add_argument("--authorization", default="")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.provider != "deterministic":
        if (
            not args.allow_paid
            or args.authorization != "I_APPROVE_PAID_AI_CALLS"
            or args.max_cases is None
            or not 1 <= args.max_cases <= 2
        ):
            parser.error("Real models require explicit consent and maximum two cases per run")
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
