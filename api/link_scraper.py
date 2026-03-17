"""
Minimal URL scraping helper.

Provides scrape_url() — plain HTTP text extraction used as a fallback by
link_fetchers._fallback_plain().
"""
import logging
import re

log = logging.getLogger("pipeline")


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
