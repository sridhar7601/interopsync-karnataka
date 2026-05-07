"""
Azure OpenAI GPT-4.1 narration overlay for the Interop Layer.

Grounded — LLM only describes pre-computed sync events, conflicts, and audit data.
Never invents UBIDs, business names, or timestamps. Disk-cached by content hash.

Brief non-negotiables:
- No hosted-LLM use on raw PII → only scrambled / synthetic data is sent.
- Production swaps Azure for on-prem Llama-3 / Mistral by changing endpoint + auth.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env.local")
load_dotenv(_BACKEND_DIR / ".env")

CACHE_DIR = _BACKEND_DIR / "data" / "llm_cache"


def _hash_key(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def _read_cache(key: str) -> str | None:
    path = CACHE_DIR / f"{key}.txt"
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


def _write_cache(key: str, text: str) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    (CACHE_DIR / f"{key}.txt").write_text(text, encoding="utf-8")


def _has_llm() -> bool:
    return bool(os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"))


def _raw_llm(system_prompt: str, user_content: str, max_tokens: int = 200) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    azure_key = os.environ.get("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if azure_key and azure_endpoint:
        with httpx.Client(timeout=30.0) as client:
            r = client.post(
                azure_endpoint,
                headers={"Content-Type": "application/json", "api-key": azure_key},
                json={"messages": messages, "max_tokens": max_tokens, "temperature": 0.2},
            )
            r.raise_for_status()
            data = r.json()
            return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()

    openai_key = os.environ.get("OPENAI_API_KEY")
    if not openai_key:
        raise RuntimeError("No LLM API key configured")
    with httpx.Client(timeout=30.0) as client:
        r = client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {openai_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.2,
            },
        )
        r.raise_for_status()
        data = r.json()
        return (data.get("choices") or [{}])[0].get("message", {}).get("content", "").strip()


# ─── 1. Dashboard briefing ────────────────────────────────────────────────────
def generate_dashboard_briefing(stats: dict[str, Any]) -> str:
    """
    stats keys:
      - total_syncs, completed, failed, conflict_count, pending_review
      - sws_to_dept, dept_to_sws, by_department (dict)
      - unresolved_conflicts, critical_conflicts
    """
    cache_key = f"briefing_{_hash_key(stats)}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    if not _has_llm():
        return (
            f"{stats.get('total_syncs', 0)} sync events processed. "
            f"{stats.get('conflict_count', 0)} conflicts detected, "
            f"{stats.get('unresolved_conflicts', 0)} await reviewer. "
            f"{stats.get('failed', 0)} failed propagations need retry."
        )

    system = (
        "You are the AI ops assistant for Karnataka Commerce & Industries' interoperability layer. "
        "Write a 3-sentence morning briefing for the integration team. Structure:\n"
        "1. Sync state: total events processed, success rate, breakdown by direction (SWS→Dept vs Dept→SWS).\n"
        "2. Conflict + failure status: unresolved conflicts (especially CRITICAL ones) + failed syncs awaiting retry.\n"
        "3. Action: which queue (conflicts vs retries) the team should clear first.\n"
        "Use plain government-administrative English. Under 70 words."
    )
    try:
        text = _raw_llm(system, json.dumps(stats), max_tokens=220)
        _write_cache(cache_key, text)
        return text
    except Exception:
        return (
            f"{stats.get('total_syncs', 0)} syncs · {stats.get('completed', 0)} completed. "
            f"{stats.get('unresolved_conflicts', 0)} conflicts await reviewer; "
            f"{stats.get('failed', 0)} syncs need retry."
        )


# ─── 2. Conflict resolution recommendation ────────────────────────────────────
def recommend_conflict_resolution(payload: dict[str, Any]) -> str:
    """
    payload keys:
      - conflict_id, ubid, business_name, field_name, severity
      - sws_value, dept_value, dept_name
      - sws_updated_at, dept_updated_at
      - resolution_strategies (list of options: SWS_WINS, DEPT_WINS, MERGE, MANUAL)
    """
    cache_key = f"conflict_{_hash_key(payload)}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    if not _has_llm():
        sws_newer = (payload.get("sws_updated_at") or "") > (payload.get("dept_updated_at") or "")
        rec = "SWS_WINS" if sws_newer else "DEPT_WINS"
        return (
            f"Field '{payload.get('field_name')}' differs between SWS and {payload.get('dept_name')}. "
            f"Recommend {rec} (most recent update). Reviewer override available."
        )

    system = (
        "You are an interoperability conflict resolver for Karnataka government systems. "
        "Two systems disagree on the same field for the same UBID. Write 2 sentences:\n"
        "1. State the disagreement (which field, what each side says, and which has the newer timestamp).\n"
        "2. Recommend ONE resolution strategy: SWS_WINS (forward-looking authority), DEPT_WINS (legacy "
        "authoritative for existing record), MERGE (both partially valid), or MANUAL (steward must decide). "
        "Justify in one phrase. Reviewer always has final say.\n"
        "Use specific values + timestamps from the payload. Under 50 words."
    )
    try:
        text = _raw_llm(system, json.dumps(payload, default=str), max_tokens=160)
        _write_cache(cache_key, text)
        return text
    except Exception:
        return (
            f"Conflict on '{payload.get('field_name')}' between SWS and {payload.get('dept_name')}. "
            f"Reviewer to choose SWS_WINS / DEPT_WINS / MERGE / MANUAL based on context."
        )


# ─── 3. Sync event audit summary ──────────────────────────────────────────────
def explain_sync_event(payload: dict[str, Any]) -> str:
    """
    payload keys:
      - sync_id, ubid, direction (sws_to_dept / dept_to_sws)
      - source_system, target_system, status
      - changed_fields (list of {field, before, after})
      - conflict_count, retry_count
    """
    cache_key = f"audit_{_hash_key(payload)}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    if not _has_llm():
        cf = payload.get("changed_fields") or []
        return (
            f"{payload.get('direction')}: {payload.get('source_system')} → {payload.get('target_system')}. "
            f"{len(cf)} field{'s' if len(cf) != 1 else ''} changed. Status: {payload.get('status')}."
        )

    system = (
        "You are an audit-trail narrator for Karnataka's interop layer. Write 1-2 sentences:\n"
        "1. Plain-English description of what propagated (which fields changed, source → target, "
        "whether it succeeded, retried, or is in conflict).\n"
        "Use specific field names. Be terse — this goes into a per-sync audit row. Under 40 words."
    )
    try:
        text = _raw_llm(system, json.dumps(payload, default=str), max_tokens=120)
        _write_cache(cache_key, text)
        return text
    except Exception:
        cf = payload.get("changed_fields") or []
        names = ", ".join((f.get("field") or "") for f in cf[:3])
        return f"Propagated {payload.get('direction')}: {names or 'no fields'} → {payload.get('target_system')}. {payload.get('status')}."


# ─── 4. Schema mapping suggestion (for new department onboarding) ─────────────
def suggest_field_mapping(payload: dict[str, Any]) -> str:
    """
    payload keys:
      - sws_field (canonical SWS field name)
      - candidate_dept_fields (list of column names from the new dept's schema sample)
      - sample_values (dict of dept_field -> sample value)
    """
    cache_key = f"mapping_{_hash_key(payload)}"
    cached = _read_cache(cache_key)
    if cached:
        return cached

    if not _has_llm():
        return f"Map SWS '{payload.get('sws_field')}' to most semantically similar field in target schema. Reviewer to confirm."

    system = (
        "You are a schema-mapping assistant for Karnataka department-system onboarding. Given an "
        "SWS canonical field and a list of candidate fields from a new department's schema (with sample "
        "values), recommend which candidate maps to it. Write 2 sentences:\n"
        "1. Recommended mapping (sws_field → dept_field) with confidence (HIGH / MEDIUM / LOW) + 1-line reason.\n"
        "2. If LOW confidence, suggest the steward review with sample data side-by-side.\n"
        "Under 40 words."
    )
    try:
        text = _raw_llm(system, json.dumps(payload, default=str), max_tokens=140)
        _write_cache(cache_key, text)
        return text
    except Exception:
        return f"Mapping for '{payload.get('sws_field')}' requires reviewer confirmation."
