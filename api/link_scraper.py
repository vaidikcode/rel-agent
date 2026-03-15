"""Fetch and extract text content from candidate URLs for evaluation."""
import re
from typing import Any


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
    """Strip HTML tags and collapse whitespace."""
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&[a-zA-Z]+;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def scrape_candidate_links(links: list[dict[str, Any]], max_links: int = 5) -> str:
    """Scrape multiple candidate links and combine into a single text block."""
    parts: list[str] = []
    for link in links[:max_links]:
        url = link.get("url", "")
        if not url:
            continue
        label = link.get("label", url)
        text = scrape_url(url)
        parts.append(f"--- {label} ({url}) ---\n{text}")
    return "\n\n".join(parts)
