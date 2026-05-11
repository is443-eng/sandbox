"""
Query OpenAI or Ollama to validate a report; parse JSON into a flat dict + composite score.

Environment (see dotenv): VALIDATION_AI_PROVIDER (ollama|openai), OLLAMA_MODEL, OPENAI_MODEL.
Using a capable judge model typically lowers Likert variance vs small local models.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests
from dotenv import load_dotenv

from .rubric import BOOLEAN_KEYS, LIKERT_KEYS, build_validator_prompt

load_dotenv()

AI_PROVIDER = os.environ.get("VALIDATION_AI_PROVIDER", "ollama").strip().lower()
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2:latest")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT = 120


def quality_composite(row: dict[str, Any]) -> float:
    """
    Higher-is-better summary (1–5 scale): inverts spurs_bias via (6 - spurs_bias).
    Primary outcome for ANOVA can be this composite or spurs_bias alone (see analyze_experiment.py).
    """
    inv_bias = 6 - int(row["spurs_bias"])
    return (
        int(row["factual_accuracy"])
        + int(row["completeness"])
        + int(row["structure"])
        + inv_bias
    ) / 4.0


def query_validator(prompt: str, provider: str | None = None) -> str:
    prov = (provider or AI_PROVIDER).lower()
    if prov == "ollama":
        url = f"{OLLAMA_HOST.rstrip('/')}/api/chat"
        body = {
            "model": OLLAMA_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You output only valid JSON. No markdown.",
                },
                {"role": "user", "content": prompt},
            ],
            "format": "json",
            "stream": False,
        }
        r = requests.post(url, json=body, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()["message"]["content"]
    if prov == "openai":
        if not OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY not set for validation.")
        url = "https://api.openai.com/v1/chat/completions"
        body = {
            "model": OPENAI_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a validation reviewer. Return only valid JSON.",
                },
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        r = requests.post(url, headers=headers, json=body, timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]
    raise ValueError(f"Unknown provider: {prov}")


def _clamp_likert(value: Any, key: str) -> int:
    """Coerce validator output to 1–5 (handles stray 0 or 6 from models)."""
    try:
        v = int(round(float(value)))
    except (TypeError, ValueError) as e:
        raise ValueError(f"{key} must be numeric 1–5, got {value!r}") from e
    return max(1, min(5, v))


def parse_validation_json(text: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"No JSON object in model response: {text[:500]}")
    data = json.loads(m.group(0))
    for k in LIKERT_KEYS:
        if k not in data:
            raise KeyError(f"Missing key {k}")
        data[k] = _clamp_likert(data[k], k)
    for k in BOOLEAN_KEYS:
        if k not in data:
            raise KeyError(f"Missing key {k}")
        if not isinstance(data[k], bool):
            data[k] = str(data[k]).lower() in ("true", "1", "yes")
    if "details" not in data:
        data["details"] = ""
    return data


def validate_report(
    report_text: str,
    source_context: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    prompt = build_validator_prompt(report_text, source_context)
    raw = query_validator(prompt, provider)
    parsed = parse_validation_json(raw)
    parsed["quality_composite"] = round(quality_composite(parsed), 4)
    parsed["raw_validator_response"] = raw
    return parsed


def validate_report_safe(
    report_text: str,
    source_context: str | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    try:
        return validate_report(report_text, source_context, provider)
    except Exception as e:
        return {
            "error": str(e),
            "factual_accuracy": None,
            "completeness": None,
            "structure": None,
            "spurs_bias": None,
            "uses_we_our_for_spurs": None,
            "opponent_named_fairly": None,
            "details": "",
            "quality_composite": None,
            "raw_validator_response": "",
        }
