"""Classify a URL into a link type so the right fetcher is used."""
import logging
from urllib.parse import urlparse

log = logging.getLogger("pipeline.classify")

_BLOG_HOSTS = {
    "medium.com", "dev.to", "hashnode.com", "substack.com", "wordpress.com",
    "ghost.io", "blogger.com", "tumblr.com", "wix.com", "squarespace.com",
    "weebly.com", "notion.so", "bearblog.dev",
}

_PORTFOLIO_KEYWORDS = {"portfolio", "projects", "about", "resume", "cv"}

LINK_TYPES = ("github", "linkedin", "paper", "blog", "web")


def infer_link_type(url: str) -> str:
    """Return one of: github, linkedin, paper, blog, web."""
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower().removeprefix("www.")
        path = parsed.path.lower()
    except Exception:
        log.debug("classify  url=%s → web (parse error)", url)
        return "web"

    if "github.com" in host or "github.io" in host:
        result = "github"
    elif "linkedin.com" in host:
        result = "linkedin"
    elif path.endswith(".pdf") or "arxiv.org" in host or "doi.org" in host or "scholar.google" in host:
        result = "paper"
    elif any(bh in host for bh in _BLOG_HOSTS):
        result = "blog"
    elif any(kw in path for kw in _PORTFOLIO_KEYWORDS):
        result = "blog"
    else:
        result = "web"

    log.info("classify  url=%s → %s", url[:80], result)
    return result
