"""Optional bounded model comparison. Output never authorizes operations."""

import json
import re
from time import perf_counter

import httpx2 as httpx

from .config import settings
from .diagnosis import Diagnosis, Snapshot, model_facts

SYSTEM = (
    "Evaluate sanitized reliability facts. Return only the supplied JSON schema. "
    "Distinguish observations from hypotheses; abstain on insufficient evidence. "
    "Never invent metrics, logs or citations. Actions are advisory only. "
    "Resume requires a supported firing queue alert, fresh evidence and scrape, ready API, "
    "positive queue, confirmed hold with TTL above 30 seconds, linked run and jobs, "
    "and no collection errors. Otherwise action must be none."
)
SCHEMA = Diagnosis.model_json_schema()


def compare(snapshot: Snapshot) -> dict:
    config = settings()
    if not config.ai_enabled or not config.ai_api_key:
        raise ValueError("AI evaluation is disabled or unconfigured")
    if config.ai_provider not in ("gemini", "openai"):
        raise ValueError("Unsupported AI provider")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", config.ai_model):
        raise ValueError("Configure a valid API model identifier")
    facts = json.dumps(model_facts(snapshot))
    started = perf_counter()
    with httpx.Client(timeout=20, trust_env=False, follow_redirects=False) as client:
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
                    "input": facts,
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
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{config.ai_model}:generateContent",
                headers={"x-goog-api-key": config.ai_api_key},
                json={
                    "systemInstruction": {"parts": [{"text": SYSTEM}]},
                    "contents": [{"role": "user", "parts": [{"text": facts}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                        "responseJsonSchema": SCHEMA,
                        "maxOutputTokens": 800,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates", [])
            if len(candidates) != 1 or candidates[0].get("finishReason") != "STOP":
                raise ValueError("Model response incomplete or blocked")
            content = [
                part["text"]
                for part in candidates[0]["content"]["parts"]
                if "text" in part and not part.get("thought")
            ]
            if len(content) != 1:
                raise ValueError("Model response ambiguous")
            usage = data.get("usageMetadata", {})
            tokens = {
                "input_tokens": usage.get("promptTokenCount"),
                "output_tokens": usage.get("candidatesTokenCount"),
            }
    if len(content[0]) > 4000:
        raise ValueError("Model response too large")
    result = Diagnosis.model_validate_json(content[0])
    return {
        "diagnosis": result.model_dump(),
        "provider": config.ai_provider,
        "model": config.ai_model,
        "usage": tokens,
        "elapsed_ms": round((perf_counter() - started) * 1000),
    }
