"""
Fetch and extract content from candidate URLs for evaluation.

Provides:
  - scrape_url          – plain HTTP fallback (kept for backward compat)
  - scrape_candidate_links – old-style combined text (still used if called directly)
  - fetch_and_store_links  – NEW: type-aware fetch pipeline, stores to DB, returns combined text
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from typing import Any
from urllib.parse import urlparse

from link_classifier import infer_link_type
from link_fetchers import (
    get_fetcher, fetch_linkedin, extract_discoverable_urls,
)

log = logging.getLogger("pipeline")

CACHE_MAX_AGE = timedelta(hours=24)

MAX_DISCOVERED_PER_CANDIDATE = 3
MAX_DISCOVERED_PER_LINK = 3

_TIER = {"blog": 0, "github": 1, "linkedin": 1, "paper": 2, "web": 2}


def _normalize_github_to_user(url: str) -> str:
    """github.com/alice/repo/... -> github.com/alice"""
    try:
        parsed = urlparse(url)
        if "github.com" not in (parsed.hostname or "").lower():
            return url
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if parts:
            return f"https://github.com/{parts[0]}"
    except Exception:
        pass
    return url


def _prioritize_links(links: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort links: portfolio/blog first, github+linkedin next, then rest.
    Deduplicates GitHub links to the same user only when multiple repo URLs
    point to the same owner — preserves the first (or explicit profile) link
    without collapsing repo URLs that the candidate intentionally shared."""
    for link in links:
        if not link.get("link_type"):
            link["link_type"] = infer_link_type(link.get("url", ""))

    seen_gh_users: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for link in links:
        if link.get("link_type") == "github":
            norm = _normalize_github_to_user(link.get("url", ""))
            if norm in seen_gh_users:
                continue
            seen_gh_users.add(norm)
        deduped.append(link)

    return sorted(deduped, key=lambda l: _TIER.get(l.get("link_type", "web"), 2))


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

def _fetch_one(url: str, link_type: str, candidate_name: str) -> dict[str, Any]:
    """Fetch a single URL with the appropriate fetcher. Returns the result dict."""
    fetcher = get_fetcher(link_type)
    if link_type == "linkedin":
        return fetch_linkedin(url, candidate_name=candidate_name)
    return fetcher(url)


def _discover_from_content(
    content_text: str,
    source_url: str,
    link_type: str,
    already_seen: set[str],
    per_link_budget: int,
) -> list[str]:
    """Extract discoverable URLs from fetched content, respecting budget and dedup."""
    urls = extract_discoverable_urls(content_text, source_url=source_url, max_urls=per_link_budget + 5)
    out: list[str] = []
    for u in urls:
        if u in already_seen or u == source_url:
            continue
        if _normalize_github_to_user(u) in already_seen:
            continue
        out.append(u)
        if len(out) >= per_link_budget:
            break
    return out


def fetch_and_store_links(
    links: list[dict[str, Any]],
    candidate_name: str = "",
    max_links: int = 10,
) -> str:
    """
    For each root link: classify → fetch → discover embedded URLs → fetch discovered (one level).
    Returns combined text for evaluation. Stores fetched content to DB.
    """
    from supabase_client import upsert_link_fetch, get_link_fetch

    prioritized = _prioritize_links(list(links))

    parts: list[str] = []
    now = datetime.now(tz=timezone.utc)
    total = min(len(prioritized), max_links)
    log.info("pipeline  starting fetch for %d links (candidate=%s)", total, candidate_name or "?")

    global_discovered_budget = MAX_DISCOVERED_PER_CANDIDATE
    all_fetched_urls: set[str] = set()

    root_results: list[dict[str, Any]] = []

    # --- Pass 1: fetch root links ---
    for i, link in enumerate(prioritized[:max_links], 1):
        url = link.get("url", "")
        if not url:
            root_results.append({})
            continue

        link_id = link.get("id")
        link_type = link.get("link_type") or infer_link_type(url)
        label = link.get("label", url)
        all_fetched_urls.add(url)
        all_fetched_urls.add(_normalize_github_to_user(url))

        log.info("pipeline  [%d/%d] type=%-10s url=%s", i, total, link_type, url[:80])

        cached = get_link_fetch(link_id) if link_id else None
        if cached:
            fetched_at_str = cached.get("fetched_at", "")
            try:
                fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00"))
                if now - fetched_at < CACHE_MAX_AGE and cached.get("content_text"):
                    log.info("pipeline  [%d/%d] cache hit (fetched %s)", i, total, fetched_at_str[:19])
                    parts.append(f"--- [{link_type}] {label} ({url}) ---\n{cached['content_text']}")
                    root_results.append({"cached": True})
                    continue
            except (ValueError, TypeError):
                pass

        log.info("pipeline  [%d/%d] fetching fresh content...", i, total)
        try:
            result = _fetch_one(url, link_type, candidate_name)
        except Exception as e:
            log.error("pipeline  [%d/%d] fetch error: %s", i, total, e)
            result = {"content_text": f"[Fetch error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}

        content_text = result.get("content_text", "")
        content_type = result.get("content_type", "text")
        metadata = dict(result.get("metadata", {}))
        error = result.get("error")

        if error:
            log.warning("pipeline  [%d/%d] fetcher returned error: %s", i, total, error)
        else:
            log.info("pipeline  [%d/%d] fetched %d chars (%s)", i, total, len(content_text), content_type)

        root_results.append({
            "link_id": link_id, "url": url, "link_type": link_type, "label": label,
            "content_text": content_text, "content_type": content_type,
            "metadata": metadata, "error": error, "index": i,
        })

    # --- Pass 2: discover and fetch from each root's content (one level) ---
    for rr in root_results:
        if not rr or rr.get("cached"):
            continue

        url = rr["url"]
        link_type = rr["link_type"]
        content_text = rr["content_text"]
        metadata = rr["metadata"]
        error = rr.get("error")
        i = rr["index"]
        label = rr["label"]
        link_id = rr.get("link_id")

        if not content_text or error:
            _store_and_append(rr, parts, link_id, now)
            continue

        per_link_cap = min(MAX_DISCOVERED_PER_LINK, global_discovered_budget)
        if per_link_cap <= 0:
            _store_and_append(rr, parts, link_id, now)
            continue

        discovered_urls = _discover_from_content(
            content_text, url, link_type, all_fetched_urls, per_link_cap,
        )
        if not discovered_urls:
            _store_and_append(rr, parts, link_id, now)
            continue

        log.info("pipeline  [%d/%d] discovered %d URL(s), fetching (budget left=%d)",
                 i, total, len(discovered_urls), global_discovered_budget)

        discovered_links: list[dict[str, Any]] = []
        for d_url in discovered_urls:
            if global_discovered_budget <= 0:
                break
            if _normalize_github_to_user(d_url) in all_fetched_urls:
                continue
            all_fetched_urls.add(d_url)
            all_fetched_urls.add(_normalize_github_to_user(d_url))
            d_type = infer_link_type(d_url)
            log.info("pipeline  [%d/%d] +discover type=%-10s url=%s", i, total, d_type, d_url[:80])
            try:
                d_result = _fetch_one(d_url, d_type, candidate_name)
                if d_result.get("error"):
                    log.debug("pipeline  discovered fetch error for %s: %s", d_url[:60], d_result["error"])
                    continue
                d_text = d_result.get("content_text", "")
                d_meta = d_result.get("metadata", {})
                content_text += f"\n\n--- [discovered {d_type}] {d_url} ---\n{d_text}"
                discovered_links.append({
                    "url": d_url,
                    "link_type": d_type,
                    "content_preview": d_text[:300],
                    "metadata": d_meta,
                })
                global_discovered_budget -= 1
            except Exception as e:
                log.debug("pipeline  discovered fetch exception for %s: %s", d_url[:60], e)

        if discovered_links:
            metadata["discovered_links"] = discovered_links
            log.info("pipeline  [%d/%d] merged %d discovered links", i, total, len(discovered_links))

        rr["content_text"] = content_text
        rr["metadata"] = metadata
        _store_and_append(rr, parts, link_id, now)

    log.info("pipeline  done, %d root links + %d discovered, total_text=%d chars",
             total, MAX_DISCOVERED_PER_CANDIDATE - global_discovered_budget, sum(len(p) for p in parts))
    return "\n\n".join(parts)


def _store_and_append(
    rr: dict[str, Any],
    parts: list[str],
    link_id: str | None,
    now: datetime,
) -> None:
    """Store fetch result to DB and append to combined text parts."""
    from supabase_client import upsert_link_fetch

    url = rr.get("url", "")
    link_type = rr.get("link_type", "web")
    label = rr.get("label", url)
    content_text = rr.get("content_text", "")
    content_type = rr.get("content_type", "text")
    metadata = rr.get("metadata", {})
    i = rr.get("index", "?")

    if link_id:
        try:
            upsert_link_fetch(
                candidate_link_id=link_id,
                link_type=link_type,
                content_type=content_type,
                content_text=content_text[:50000],
                metadata=metadata,
            )
            log.info("pipeline  [%s] stored to DB", i)
        except Exception as e:
            log.error("pipeline  [%s] failed to store in DB: %s", i, e)

    parts.append(f"--- [{link_type}] {label} ({url}) ---\n{content_text}")
