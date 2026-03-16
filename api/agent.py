"""
LangGraph evaluation agent.
Evaluates a candidate against bucket requirements using scraped link content.

Gemini key pool: loads GOOGLE_API_KEY_1 … _N from env and rotates
automatically when a key hits 429 / RESOURCE_EXHAUSTED.
"""
import logging
import os
import threading
import time
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

log = logging.getLogger("llm")

GEMINI_MODEL = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# Key pool
# ---------------------------------------------------------------------------

_KEY_POOL: list[str] = []
_key_idx: int = 0
_key_lock = threading.Lock()


def _load_keys() -> list[str]:
    """Scan env for GOOGLE_API_KEY_1 … _N, fall back to single key."""
    global _KEY_POOL
    keys: list[str] = []
    for i in range(1, 21):
        k = os.environ.get(f"GOOGLE_API_KEY_{i}", "").strip()
        if k:
            keys.append(k)
    if not keys:
        single = (os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY") or "").strip()
        if single:
            keys.append(single)
    _KEY_POOL = keys
    log.info("loaded %d Gemini API key(s)", len(keys))
    return keys


def _current_key() -> str:
    if not _KEY_POOL:
        _load_keys()
    if not _KEY_POOL:
        raise RuntimeError("No Gemini API keys found (set GOOGLE_API_KEY_1 … _N)")
    with _key_lock:
        return _KEY_POOL[_key_idx % len(_KEY_POOL)]


def _rotate_key() -> str:
    global _key_idx
    with _key_lock:
        _key_idx = (_key_idx + 1) % len(_KEY_POOL)
        chosen = _KEY_POOL[_key_idx]
    log.warning("rotated to key slot %d/%d", _key_idx + 1, len(_KEY_POOL))
    return chosen


def _is_quota_error(e: BaseException) -> bool:
    msg = (getattr(e, "message", "") or str(e)).upper()
    return any(tok in msg for tok in ("429", "RESOURCE_EXHAUSTED", "QUOTA", "RATE_LIMIT"))


# ---------------------------------------------------------------------------
# LLM helpers
# ---------------------------------------------------------------------------

def _get_llm(api_key: str | None = None):
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=api_key or _current_key(),
        temperature=0.1,
        max_retries=0,
    )


def llm_invoke(messages: list, *, max_retries: int | None = None) -> Any:
    """Invoke Gemini with automatic key rotation on quota / rate-limit errors."""
    if not _KEY_POOL:
        _load_keys()
    retries = max_retries if max_retries is not None else max(len(_KEY_POOL), 2)
    last_err: BaseException | None = None
    for attempt in range(1, retries + 1):
        key = _current_key()
        llm = _get_llm(key)
        try:
            return llm.invoke(messages)
        except Exception as e:
            if _is_quota_error(e) and attempt < retries:
                log.warning("key %d/%d quota hit (attempt %d): %s – rotating",
                            (_key_idx % len(_KEY_POOL)) + 1, len(_KEY_POOL), attempt, str(e)[:120])
                _rotate_key()
                time.sleep(1)
                last_err = e
                continue
            raise
    raise last_err or RuntimeError("All Gemini API keys exhausted")


class RequirementVerdict(TypedDict):
    passed: bool
    reason: str


def _message_content_to_str(content: str | list) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            (c.get("text", c) if isinstance(c, dict) else str(c)) for c in content
        )
    return str(content)


def _eval_all_prompt(candidate_text: str, requirements: list[dict[str, Any]]) -> str:
    req_block = "\n\n".join(
        f'- id: "{r["id"]}"\n  label: {r.get("label", r["id"])}\n  what to check: {r.get("prompt", "")}'
        for r in requirements
    )
    return f"""Evaluate the candidate against ALL of the following requirements in one go.

Candidate information (scraped from their online profiles):
---
{candidate_text[:14000]}
---

Requirements (use the exact "id" string in your response):
{req_block}

Return a single JSON array with one object per requirement. Each object must have:
- "requirement_id": the exact id string from the list above
- "passed": true or false
- "reason": one short sentence explaining why

Example: [{{"requirement_id": "...", "passed": true, "reason": "..."}}, ...]
Return only the JSON array, no other text."""


def _parse_batched_verdicts(response_text: str, requirement_ids: list[str]) -> dict[str, RequirementVerdict]:
    if not isinstance(response_text, str):
        response_text = _message_content_to_str(response_text)
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    results: dict[str, RequirementVerdict] = {}
    for rid in requirement_ids:
        results[rid] = {"passed": False, "reason": "Not evaluated"}
    try:
        import json as _json
        arr = _json.loads(text)
        if not isinstance(arr, list):
            return results
        for item in arr:
            if not isinstance(item, dict):
                continue
            rid = item.get("requirement_id")
            if rid not in results:
                continue
            passed = item.get("passed", False)
            if isinstance(passed, str):
                passed = passed.strip().upper() in ("TRUE", "YES", "1")
            reason = (item.get("reason") or "").strip() or "No reason given"
            results[rid] = {"passed": bool(passed), "reason": reason}
    except Exception:
        pass
    return results


def run_candidate_evaluation(candidate_text: str, requirements: list[dict[str, Any]]) -> dict[str, RequirementVerdict]:
    """Evaluate a candidate's scraped content against all requirements in one LLM call.
    Returns { requirement_id: { passed, reason } }."""
    if not requirements:
        raise ValueError("At least one requirement is needed for evaluation")
    prompt = _eval_all_prompt(candidate_text, requirements)
    msg = llm_invoke([
        SystemMessage(content="You are a strict but fair candidate evaluator. Output only the JSON array."),
        HumanMessage(content=prompt),
    ])
    content = msg.content if hasattr(msg, "content") else str(msg)
    return _parse_batched_verdicts(_message_content_to_str(content), [r["id"] for r in requirements])


# ---------------------------------------------------------------------------
# Structured candidate details extraction (post-evaluation)
# ---------------------------------------------------------------------------

def extract_candidate_details(
    candidate_text: str,
    verdicts: dict[str, RequirementVerdict],
    requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Extract structured candidate details from scraped content and evaluation verdicts.
    Returns a dict suitable for evaluation_details JSON: experience_summary, education,
    key_skills_evidence, strengths, concerns, fit_summary."""
    verdict_summary = "\n".join(
        f"- {next((r.get('label', r['id']) for r in requirements if r['id'] == rid), rid)}: {'Pass' if v['passed'] else 'Fail'} — {v.get('reason', '')}"
        for rid, v in verdicts.items()
    )
    prompt = f"""Based on the candidate information and evaluation results below, extract structured details.

Candidate information (from their profiles):
---
{candidate_text[:14000]}
---

Evaluation results:
{verdict_summary}

Respond with a single JSON object (no markdown, no code fence) with exactly these keys:
- experience_summary: string (2–4 sentences on work history and role relevance)
- education: string (degrees, institutions if mentioned; "Not mentioned" if absent)
- key_skills_evidence: string (concrete evidence from profiles for top skills; brief)
- strengths: array of strings (3–6 bullet points: what makes them strong for the role)
- concerns: array of strings (0–4 bullet points: gaps or risks; empty array if none)
- fit_summary: string (2–3 sentences overall fit and recommendation)"""

    msg = llm_invoke([
        SystemMessage(content="You are an analyst. Output only valid JSON with the requested keys. No other text."),
        HumanMessage(content=prompt),
    ])
    content = _message_content_to_str(msg.content if hasattr(msg, "content") else str(msg))
    # Strip markdown code block if present
    raw = content.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
    if raw.endswith("```"):
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        import json
        out = json.loads(raw)
    except Exception:
        out = {}
    # Normalize types
    if not isinstance(out.get("strengths"), list):
        out["strengths"] = [s.strip() for s in str(out.get("strengths", "")).split("\n") if s.strip()][:8]
    if not isinstance(out.get("concerns"), list):
        out["concerns"] = [s.strip() for s in str(out.get("concerns", "")).split("\n") if s.strip()][:6]
    for key in ("experience_summary", "education", "key_skills_evidence", "fit_summary"):
        if not isinstance(out.get(key), str):
            out[key] = str(out.get(key, "") or "")
    return {
        "experience_summary": (out.get("experience_summary") or "").strip() or None,
        "education": (out.get("education") or "").strip() or None,
        "key_skills_evidence": (out.get("key_skills_evidence") or "").strip() or None,
        "strengths": [s for s in (out.get("strengths") or []) if s][:8],
        "concerns": [s for s in (out.get("concerns") or []) if s][:6],
        "fit_summary": (out.get("fit_summary") or "").strip() or None,
    }
