"""
Shared LLM infrastructure.

Gemini key pool: loads GOOGLE_API_KEY_1 … _N from env and rotates
automatically when a key hits 429 / RESOURCE_EXHAUSTED.

Public surface used by discovery_agent and eval_agent:
  - llm_invoke, _message_content_to_str, RequirementVerdict
  - _current_key, _load_keys, _KEY_POOL, GEMINI_MODEL, _get_llm
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


# ---------------------------------------------------------------------------
# Shared types and parsing helpers
# ---------------------------------------------------------------------------

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


def _parse_batched_verdicts(response_text: str, requirement_ids: list[str]) -> dict[str, RequirementVerdict]:
    """Parse a JSON array of {requirement_id, passed, reason} from LLM output."""
    import json as _json

    if not isinstance(response_text, str):
        response_text = _message_content_to_str(response_text)
    text = response_text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    results: dict[str, RequirementVerdict] = {}
    for rid in requirement_ids:
        results[rid] = {"passed": False, "reason": "Not evaluated"}
    try:
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
