"""Optional bounded model comparison. Output never authorizes operations."""

import json
import re
from copy import deepcopy
from itertools import combinations
from time import perf_counter

import httpx2 as httpx

from .config import settings
from .diagnosis import Diagnosis, Snapshot, deterministic, model_facts

SYSTEM = (
    "Classify sanitized observations using this ORDERED decision table. "
    "Stop at the first matching row. Do not infer any unsupplied measurement.\n"
    "1. If alert=unsupported OR target_supported is not true, "
    "incident_status is not firing, or evidence_fresh "
    "is not true: cause=insufficient_evidence, action=none.\n"
    "2. Alert OpsProofDemoAPIUnavailable AND api_ready=false: cause=api_unreachable, action=none.\n"
    "3. Alert OpsProofDemoDependenciesUnavailable AND scrape_fresh=true AND api_ready=false: "
    "cause=dependency_unavailable, action=none.\n"
    "4. For alert OpsProofDemoQueueBacklog, evaluate these rows IN ORDER:\n"
    "4a. If scrape_fresh is not true OR api_ready is not true OR queued is null OR queued<=0: "
    "cause=insufficient_evidence, action=none. STOP; a firing alert does not override queued=0.\n"
    "4b. Otherwise, worker_paused is not true: cause=queue_stalled_unknown, action=none.\n"
    "4c. Otherwise: cause=demo_worker_paused. action=resume_demo_worker ONLY WHEN "
    "hold_ttl_seconds>30 AND linked_run=true AND linked_job_count>0 AND linked_jobs_unique=true "
    "AND collection_errors=false. If any condition is missing or fails, action=none.\n"
    "Missing job links NEVER change a confirmed demo_worker_paused cause; they only block resume.\n"
    "5. All remaining cases: cause=insufficient_evidence, action=none.\n"
    "Return the exact JSON schema. explanation: ONE short complete sentence, aim below160 "
    "characters, state the decisive supplied observation only. Evidence references must be "
    "distinct and relevant. Zero linked jobs means missing links, not observed duplicates. "
    "queued counts waiting jobs; processing counts in-flight jobs, "
    "never consumers. No invented causal claims or operational commands. Actions are advisory."
)
SCHEMA = Diagnosis.model_json_schema()
SCHEMA["properties"]["evidence"]["uniqueItems"] = True
NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
NVIDIA_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
NVIDIA_SERVING_MODEL = "private/nvidia/nemotron-3.5-super-120b-a12b"
NVIDIA_MAX_OUTPUT_TOKENS = 8192
NVIDIA_REASONING_EFFORT = "low"
NVIDIA_EVIDENCE_REASONING_EFFORT = "low"
NVIDIA_EVIDENCE_MAX_OUTPUT_TOKENS = 16384
NVIDIA_EVIDENCE_TIMEOUT_SECONDS = 240
NVIDIA_TEMPERATURE = 1.0
NVIDIA_TOP_P = 0.95
NVIDIA_SEED = 42


def nvidia_schema(value):
    """Translate schema keywords without rewriting property names or literal data."""
    if isinstance(value, dict):
        translated = {}
        for name, item in value.items():
            if name == "uniqueItems":
                # The wire grammar rejects this keyword; local validation still enforces it.
                continue
            if name in (
                "properties",
                "$defs",
                "definitions",
                "patternProperties",
                "dependentSchemas",
            ):
                translated[name] = {key: nvidia_schema(schema) for key, schema in item.items()}
            elif name in ("allOf", "anyOf", "oneOf", "prefixItems"):
                translated[name] = [nvidia_schema(schema) for schema in item]
            elif name in (
                "items",
                "additionalProperties",
                "unevaluatedProperties",
                "unevaluatedItems",
                "contains",
                "propertyNames",
                "not",
                "if",
                "then",
                "else",
                "contentSchema",
            ):
                translated[name] = nvidia_schema(item)
            else:
                translated[name] = deepcopy(item)
        if (
            value.get("type") == "array"
            and value.get("uniqueItems") is True
            and isinstance(value.get("items"), dict)
            and "enum" in value["items"]
        ):
            # The six runtime evidence keys have only64 canonical subsets. Their
            # enum enforces uniqueness on the wire without unsupported uniqueItems.
            choices = value["items"]["enum"]
            if len(choices) <= 6 and all(isinstance(choice, str) for choice in choices):
                minimum = value.get("minItems", 0)
                maximum = min(value.get("maxItems", len(choices)), len(choices))
                translated["enum"] = [
                    list(group)
                    for size in range(minimum, maximum + 1)
                    for group in combinations(choices, size)
                ]
                if "enum" in value:
                    translated["enum"] = [
                        group for group in translated["enum"] if group in value["enum"]
                    ]
        if translated.get("type") == "object" and "oneOf" in translated:
            # Spell out complete alternatives after an observed composed-schema
            # response omitted shared required fields; provider internals are unknown.
            common = {name: item for name, item in translated.items() if name != "oneOf"}
            alternatives = []
            for branch in translated["oneOf"]:
                alternatives.append(_schema_intersection(common, branch))
            return {"oneOf": alternatives}
        return translated
    if isinstance(value, list):
        return [nvidia_schema(item) for item in value]
    return value


def _schema_intersection(common: dict, branch: dict) -> dict:
    """Expand our object alternatives; reject unsupported overlapping constraints."""
    complete = deepcopy(common)
    for name, constraint in branch.items():
        if name not in complete or complete[name] == constraint:
            complete[name] = deepcopy(constraint)
        elif name == "properties":
            for field, schema in constraint.items():
                complete[name][field] = _schema_intersection(complete[name].get(field, {}), schema)
        elif name == "required":
            complete[name] = list(dict.fromkeys(complete[name] + constraint))
        elif name == "enum":
            complete[name] = [item for item in complete[name] if item in constraint]
            if not complete[name]:
                raise ValueError("Incompatible NVIDIA schema alternatives")
        else:
            raise ValueError(f"Unsupported NVIDIA schema constraint intersection: {name}")
    return complete


def nvidia_body(model: str, facts: dict, *, system: str, schema: dict) -> dict:
    """One shared request contract for runtime and separately authorized evaluation."""
    if not re.fullmatch(r"nvidia/[A-Za-z0-9._-]{1,100}", model):
        raise ValueError("Configure an NVIDIA model identifier")
    request_schema = deepcopy(schema)
    signals = request_schema.get("properties", {}).get("supporting_signals")
    if signals is not None:
        # Bind citations to this observation, never to a global list of possible fields.
        paths = evidence_paths(
            {
                name: value
                for name, value in facts.items()
                if name not in ("context", "evidence_contract")
            }
        )
        request_schema["properties"]["supporting_signals"] = {
            "type": "object",
            "additionalProperties": False,
            "properties": {path: {"type": "boolean", "const": True} for path in paths},
            "maxProperties": 6,
        }
        for branch in request_schema.get("oneOf", []):
            properties = branch.get("properties", {})
            if properties.get("abstained", {}).get("const") is False:
                properties["supporting_signals"] = {"minProperties": 1}
    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(facts)},
        ],
        "stream": False,
        "max_tokens": NVIDIA_EVIDENCE_MAX_OUTPUT_TOKENS
        if signals is not None
        else NVIDIA_MAX_OUTPUT_TOKENS,
        "reasoning_effort": NVIDIA_EVIDENCE_REASONING_EFFORT
        if signals is not None
        else NVIDIA_REASONING_EFFORT,
        "temperature": NVIDIA_TEMPERATURE,
        "top_p": NVIDIA_TOP_P,
        "seed": NVIDIA_SEED,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "diagnosis",
                "strict": True,
                "schema": nvidia_schema(request_schema),
            },
        },
    }


def evidence_paths(facts: dict) -> list[str]:
    """Catalog existing JSON paths; containing objects can establish missing fields."""
    paths = []

    def visit(value, prefix="", depth=0):
        if depth > 8:
            raise ValueError("Evidence nesting exceeds the supported limit")
        if isinstance(value, dict):
            children = (
                (name, item)
                for name, item in value.items()
                if isinstance(name, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name)
            )
        elif isinstance(value, list):
            children = ((str(index), item) for index, item in enumerate(value))
        else:
            return
        for name, item in children:
            path = f"{prefix}.{name}" if prefix else name
            paths.append(path)
            if len(paths) > 256:
                raise ValueError("Evidence path count exceeds the supported limit")
            visit(item, path, depth + 1)

    visit(facts)
    if not paths:
        raise ValueError("No addressable evidence fields supplied")
    return sorted(paths)


def nvidia_output(data: dict) -> tuple[str, dict]:
    """Reject partial, ambiguous, refused or tool-bearing answers before parsing JSON."""
    if data.get("model") != NVIDIA_SERVING_MODEL:
        raise ValueError("Model response serving identity changed")
    choices = data.get("choices", [])
    if len(choices) != 1 or choices[0].get("finish_reason") != "stop":
        raise ValueError("Model response incomplete or blocked")
    message = choices[0].get("message", {})
    answer = message.get("content")
    if (
        message.get("tool_calls")
        or message.get("function_call") is not None
        or message.get("refusal")
        or not isinstance(answer, str)
    ):
        raise ValueError("Model response ambiguous")
    if len(answer) > 4000:
        raise ValueError("Model response too large")
    usage = data.get("usage", {})
    return answer, {
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
    }


def diagnosis_output(answer: str) -> Diagnosis:
    result = Diagnosis.model_validate(model_json(answer))
    if len(set(result.evidence)) != len(result.evidence):
        raise ValueError("Model cited duplicate evidence references")
    return result


def model_json(answer: str) -> dict:
    """Reject duplicate JSON keys instead of accepting a last-value-wins answer."""

    def unique_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Model returned duplicate JSON keys")
            result[key] = value
        return result

    result = json.loads(answer, object_pairs_hook=unique_pairs)
    if not isinstance(result, dict):
        raise ValueError("Expected a JSON object")
    return result


def decode_evidence_selection(raw: dict, allowed_paths: set[str], *, minimum: int = 0) -> dict:
    """Losslessly project selected true-only wire keys to the public citation list."""
    selection = raw.get("supporting_signals")
    if not isinstance(selection, dict) or not set(selection) <= allowed_paths:
        raise ValueError("Model evidence selection differs from the wire schema")
    if any(selected is not True for selected in selection.values()):
        raise ValueError("Only selected true-valued evidence keys may be emitted")
    selected = sorted(selection)
    if len(selected) > 6:
        raise ValueError("Model selected too many evidence references")
    if len(selected) < minimum:
        raise ValueError("Model output requires at least one selected evidence reference")
    return {**raw, "supporting_signals": selected}


def grounded_diagnosis(answer: str, snapshot: Snapshot) -> Diagnosis:
    """Enforce cause/action policy agreement; prose and citation grounding need review."""
    result = diagnosis_output(answer)
    baseline = deterministic(snapshot)
    if result.cause != baseline.cause or result.action != baseline.action:
        raise ValueError("Model diagnosis contradicts verified operational policy")
    return result


def compare(snapshot: Snapshot) -> dict:
    config = settings()
    if not config.ai_enabled or not config.ai_api_key:
        raise ValueError("AI evaluation is disabled or unconfigured")
    if config.ai_provider not in ("nvidia", "openai"):
        raise ValueError("Unsupported AI provider")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}(?:/[A-Za-z0-9._-]{1,100})?", config.ai_model):
        raise ValueError("Configure a valid API model identifier")
    if config.ai_provider == "nvidia" and not config.ai_model.startswith("nvidia/"):
        raise ValueError("Configure an NVIDIA model identifier")
    if config.ai_provider == "nvidia" and config.ai_model != NVIDIA_MODEL:
        raise ValueError("NVIDIA configuration differs from the selected route")
    facts = model_facts(snapshot)
    started = perf_counter()
    with httpx.Client(
        timeout=120 if config.ai_provider == "nvidia" else 20,
        trust_env=False,
        follow_redirects=False,
        transport=httpx.HTTPTransport(retries=0),
    ) as client:
        if config.ai_provider == "openai":
            response = client.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {config.ai_api_key}",
                },
                json={
                    "model": config.ai_model,
                    "store": False,
                    "instructions": SYSTEM,
                    "input": json.dumps(facts),
                    "max_output_tokens": 800,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "diagnosis",
                            "strict": True,
                            "schema": SCHEMA,
                        }
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "completed":
                raise ValueError("Model response incomplete")
            content = [
                part["text"]
                for item in data.get("output", [])
                for part in item.get("content", [])
                if part.get("type") == "output_text"
            ]
            if len(content) != 1:
                raise ValueError("Model response refused or ambiguous")
            usage = data.get("usage", {})
            tokens = {
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
            }
        else:
            response = client.post(
                NVIDIA_ENDPOINT,
                headers={"Authorization": f"Bearer {config.ai_api_key}"},
                json=nvidia_body(config.ai_model, facts, system=SYSTEM, schema=SCHEMA),
            )
            response.raise_for_status()
            if response.status_code != 200:
                raise ValueError("Model response pending or incomplete")
            data = response.json()
            answer, tokens = nvidia_output(data)
            content = [answer]
    if len(content[0]) > 4000:
        raise ValueError("Model response too large")
    result = grounded_diagnosis(content[0], snapshot)
    return {
        "diagnosis": result.model_dump(),
        "provider": config.ai_provider,
        "model": config.ai_model,
        "usage": tokens,
        "elapsed_ms": round((perf_counter() - started) * 1000),
    }
