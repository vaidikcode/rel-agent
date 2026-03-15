"""
Fetch and extract content from candidate URLs for evaluation.

Provides:
  - scrape_url          – plain HTTP fallback (kept for backward compat)
  - scrape_candidate_links – old-style combined text (still used if called directly)
  - fetch_and_store_links  – NEW: type-aware fetch pipeline, stores to DB, returns combined text
"""
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any

from link_classifier import infer_link_type
from link_fetchers import get_fetcher, fetch_linkedin

log = logging.getLogger("pipeline")

CACHE_MAX_AGE = timedelta(hours=24)


# ---------------------------------------------------------------------------
# Plain HTTP helpers  (kept as fallback)
# ---------------------------------------------------------------------------

def scrape_url(url: str, timeout: int = 10) -> str:
    """Fetch a URL and return cleaned text content (max ~8000 chars)."""
    import requests
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MireloBot/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
    except Exception as e:
        return f"[Error fetching {url}: {e}]"

    content_type = resp.headers.get("content-type", "")
    if "html" in content_type:
        return _extract_text_from_html(resp.text)[:8000]
    elif "json" in content_type:
        return resp.text[:8000]
    elif "text" in content_type:
        return resp.text[:8000]
    return f"[Non-text content: {content_type}]"


def _extract_text_from_html(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scrape_candidate_links(links: list[dict[str, Any]], max_links: int = 5) -> str:
    """Legacy: scrape multiple candidate links with plain HTTP."""
    parts: list[str] = []
    for link in links[:max_links]:
        url = link.get("url", "")
        if not url:
            continue
        label = link.get("label", url)
        text = scrape_url(url)
        parts.append(f"--- {label} ({url}) ---\n{text}")
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Type-aware fetch pipeline  (main entry point for evaluation)
# ---------------------------------------------------------------------------

def fetch_and_store_links(
    links: list[dict[str, Any]],
    candidate_name: str = "",
    max_links: int = 10,
) -> str:
    """
    For each link: classify type → fetch with appropriate fetcher → store to DB.
    Returns combined text for evaluation.
    Uses cached content if fetched less than CACHE_MAX_AGE ago.
    """
    from supabase_client import upsert_link_fetch, get_link_fetch

    parts: list[str] = []
    now = datetime.now(tz=timezone.utc)
    total = min(len(links), max_links)
    log.info("pipeline  starting fetch for %d links (candidate=%s)", total, candidate_name or "?")

    for i, link in enumerate(links[:max_links], 1):
        url = link.get("url", "")
        if not url:
            continue

        link_id = link.get("id")
        link_type = link.get("link_type") or infer_link_type(url)
        label = link.get("label", url)

        log.info("pipeline  [%d/%d] type=%-10s url=%s", i, total, link_type, url[:80])

        cached = get_link_fetch(link_id) if link_id else None
        if cached:
            fetched_at_str = cached.get("fetched_at", "")
            try:
                fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                if now - fetched_at < CACHE_MAX_AGE and cached.get("content_text"):
                    log.info("pipeline  [%d/%d] cache hit (fetched %s)", i, total, fetched_at_str[:19])
                    parts.append(f"--- [{link_type}] {label} ({url}) ---\n{cached['content_text']}")
                    continue
            except (ValueError, TypeError):
                pass

        log.info("pipeline  [%d/%d] fetching fresh content...", i, total)
        try:
            fetcher = get_fetcher(link_type)
            if link_type == "linkedin":
                result = fetch_linkedin(url, candidate_name=candidate_name)
            else:
                result = fetcher(url)
        except Exception as e:
            log.error("pipeline  [%d/%d] fetch error: %s", i, total, e)
            result = {"content_text": f"[Fetch error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}

        content_text = result.get("content_text", "")
        content_type = result.get("content_type", "text")
        metadata = result.get("metadata", {})
        error = result.get("error")

        if error:
            log.warning("pipeline  [%d/%d] fetcher returned error: %s", i, total, error)
        else:
            log.info("pipeline  [%d/%d] fetched %d chars (%s)", i, total, len(content_text), content_type)

        if link_id:
            try:
                upsert_link_fetch(
                    candidate_link_id=link_id,
                    link_type=link_type,
                    content_type=content_type,
                    content_text=content_text[:50000],
                    metadata=metadata,
                )
                log.info("pipeline  [%d/%d] stored to DB", i, total)
            except Exception as e:
                log.error("pipeline  [%d/%d] failed to store in DB: %s", i, total, e)

        parts.append(f"--- [{link_type}] {label} ({url}) ---\n{content_text}")

    log.info("pipeline  done, %d links processed, total_text=%d chars", total, sum(len(p) for p in parts))
    return "\n\n".join(parts)
