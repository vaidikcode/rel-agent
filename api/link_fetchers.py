"""
Link-type-aware fetchers.

Each fetcher returns a dict with:
  content_text  – the extracted text / markdown
  content_type  – "markdown" | "json" | "text"
  metadata      – dict of structured extras (e.g. GitHub stars)
  error         – optional error string if something went wrong
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any
from urllib.parse import urlparse, urljoin, urldefrag

log = logging.getLogger("pipeline.fetch")

# ---------------------------------------------------------------------------
# URL extraction helpers
# ---------------------------------------------------------------------------

_GITHUB_URL_RE = re.compile(
    r"https?://(?:www\.)?github\.com/([a-zA-Z0-9_.-]+)(?:/([a-zA-Z0-9_.-]+))?(?:/[^\s)\]]*)?",
    re.IGNORECASE,
)

_ANY_URL_RE = re.compile(r"https?://[^\s\"'<>\)\]\}]+", re.IGNORECASE)

_ALLOWED_DISCOVERY_HOSTS = {
    "github.com", "linkedin.com", "arxiv.org", "doi.org",
    "scholar.google.com", "semanticscholar.org",
    "medium.com", "dev.to", "substack.com",
}

_NOISE_PATH_TOKENS = {
    "login", "logout", "signin", "signup", "share", "intent",
    "auth", "oauth", "settings", "notifications", "help", "support",
    "terms", "privacy", "policy", "status", "jobs",
}


def extract_github_urls_from_text(text: str, max_urls: int = 10) -> list[str]:
    """Extract unique, normalized github.com URLs from page content."""
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _GITHUB_URL_RE.finditer(text):
        owner = (m.group(1) or "").strip()
        repo = (m.group(2) or "").strip()
        if not owner or owner.lower() in ("settings", "notifications", "orgs", "explore", "topics"):
            continue
        if repo and repo.lower() not in ("settings", "notifications"):
            url = f"https://github.com/{owner}/{repo}"
        else:
            url = f"https://github.com/{owner}"
        if url not in seen:
            seen.add(url)
            out.append(url)
            if len(out) >= max_urls:
                break
    return out


def extract_discoverable_urls(
    text: str,
    source_url: str | None = None,
    max_urls: int = 15,
) -> list[str]:
    """Extract URLs worth fetching from page content.

    Keeps: allowed-domain URLs + same-origin URLs (for portfolio subpages).
    Skips: login/auth noise, fragments, duplicates.
    """
    if not text:
        return []

    source_host: str | None = None
    if source_url:
        try:
            source_host = (urlparse(source_url).hostname or "").lower().removeprefix("www.")
        except Exception:
            pass

    seen: set[str] = set()
    out: list[str] = []

    for m in _ANY_URL_RE.finditer(text):
        raw = m.group(0).rstrip(".,;:!?)'\"")
        defragged, _ = urldefrag(raw)
        if not defragged or defragged in seen:
            continue

        try:
            parsed = urlparse(defragged)
            host = (parsed.hostname or "").lower().removeprefix("www.")
            path = parsed.path.lower()
        except Exception:
            continue

        path_parts = {p for p in path.split("/") if p}
        if path_parts & _NOISE_PATH_TOKENS:
            continue

        is_allowed = any(host.endswith(ah) for ah in _ALLOWED_DISCOVERY_HOSTS)
        is_same_origin = source_host and host == source_host

        if not is_allowed and not is_same_origin:
            continue

        seen.add(defragged)
        out.append(defragged)
        if len(out) >= max_urls:
            break

    return out


# ---------------------------------------------------------------------------
# GitHub  (Official REST API)
# ---------------------------------------------------------------------------

def fetch_github(url: str) -> dict[str, Any]:
    """Fetch GitHub user or repo data via the REST API."""
    import requests

    log.info("github    fetching url=%s", url)
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip("/").split("/") if p]
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
        log.debug("github    using auth token")

    try:
        if len(parts) == 1:
            log.info("github    fetching user profile: %s", parts[0])
            result = _fetch_github_user(parts[0], headers)
        elif len(parts) >= 2 and parts[1] not in ("settings", "notifications"):
            log.info("github    fetching repo: %s/%s", parts[0], parts[1])
            result = _fetch_github_repo(parts[0], parts[1], headers)
        else:
            log.info("github    fetching user profile: %s", parts[0])
            result = _fetch_github_user(parts[0], headers)
        log.info("github    done, content_length=%d", len(result.get("content_text", "")))
        return result
    except Exception as e:
        log.error("github    failed url=%s error=%s", url, e)
        return {"content_text": f"[GitHub API error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}


def _fetch_github_user(username: str, headers: dict) -> dict[str, Any]:
    import requests

    user_r = requests.get(f"https://api.github.com/users/{username}", headers=headers, timeout=10)
    user_r.raise_for_status()
    user = user_r.json()

    repos_r = requests.get(
        f"https://api.github.com/users/{username}/repos",
        headers=headers,
        params={"per_page": 100, "sort": "pushed", "type": "owner"},
        timeout=10,
    )
    repos = repos_r.json() if repos_r.ok else []
    if isinstance(repos, list):
        repos.sort(key=lambda r: r.get("stargazers_count", 0) if isinstance(r, dict) else 0, reverse=True)

    # Profile README (special username/username repo)
    profile_readme = ""
    try:
        readme_r = requests.get(
            f"https://api.github.com/repos/{username}/{username}/readme",
            headers=headers, timeout=10,
        )
        if readme_r.ok:
            import base64
            readme_data = readme_r.json()
            content_b64 = readme_data.get("content", "")
            profile_readme = base64.b64decode(content_b64).decode("utf-8", errors="replace")[:6000]
            log.info("github    fetched profile README for @%s (%d chars)", username, len(profile_readme))
    except Exception as e:
        log.debug("github    profile README fetch failed for @%s: %s", username, e)

    # Social accounts (LinkedIn, Twitter, etc.)
    social_accounts: list[dict[str, str]] = []
    try:
        social_r = requests.get(
            f"https://api.github.com/users/{username}/social_accounts",
            headers=headers, timeout=10,
        )
        if social_r.ok:
            social_accounts = social_r.json() or []
            log.info("github    fetched %d social accounts for @%s", len(social_accounts), username)
    except Exception as e:
        log.debug("github    social accounts fetch failed for @%s: %s", username, e)

    # Organizations
    orgs: list[dict[str, Any]] = []
    try:
        orgs_r = requests.get(
            f"https://api.github.com/users/{username}/orgs",
            headers=headers, timeout=10,
        )
        if orgs_r.ok:
            orgs = orgs_r.json() or []
            log.info("github    fetched %d orgs for @%s", len(orgs), username)
    except Exception as e:
        log.debug("github    orgs fetch failed for @%s: %s", username, e)

    top_repos = [
        {"name": r["name"], "stars": r.get("stargazers_count", 0),
         "language": r.get("language"), "description": r.get("description", ""),
         "url": r.get("html_url", "")}
        for r in repos[:15] if isinstance(r, dict)
    ]

    languages: set[str] = set()
    total_stars = 0
    for r in repos:
        if isinstance(r, dict):
            if r.get("language"):
                languages.add(r["language"])
            total_stars += r.get("stargazers_count", 0)

    meta: dict[str, Any] = {
        "username": user.get("login"),
        "name": user.get("name"),
        "bio": user.get("bio"),
        "company": user.get("company"),
        "location": user.get("location"),
        "blog": user.get("blog"),
        "email": user.get("email"),
        "twitter_username": user.get("twitter_username"),
        "hireable": user.get("hireable"),
        "public_repos": user.get("public_repos", 0),
        "followers": user.get("followers", 0),
        "total_stars": total_stars,
        "languages": sorted(languages),
        "top_repos": top_repos,
        "social_accounts": [
            {"provider": s.get("provider", ""), "url": s.get("url", "")}
            for s in social_accounts if isinstance(s, dict)
        ],
        "organizations": [
            {"login": o.get("login", ""), "description": o.get("description", "")}
            for o in orgs[:10] if isinstance(o, dict)
        ],
    }

    blog_url = (user.get("blog") or "").strip()
    twitter = (user.get("twitter_username") or "").strip()
    email = (user.get("email") or "").strip()

    lines = [
        f"GitHub: {user.get('name', username)} (@{username})",
        f"Bio: {user.get('bio', 'N/A')}",
        f"Company: {user.get('company', 'N/A')}",
        f"Location: {user.get('location', 'N/A')}",
        f"Website: {blog_url or 'N/A'}",
        f"Email: {email or 'N/A'}",
        f"Twitter: @{twitter}" if twitter else "Twitter: N/A",
        f"Hireable: {user.get('hireable', 'N/A')}",
        f"Public repos: {user.get('public_repos', 0)} | Followers: {user.get('followers', 0)} | Stars: {total_stars}",
        f"Languages: {', '.join(sorted(languages)) or 'N/A'}",
    ]

    if orgs:
        lines.append(f"Organizations: {', '.join(o.get('login', '') for o in orgs[:10])}")

    if social_accounts:
        lines.append("Social accounts:")
        for s in social_accounts:
            if isinstance(s, dict):
                lines.append(f"  - {s.get('provider', '?')}: {s.get('url', '')}")

    lines.append("")
    lines.append("Top repositories (by stars):")
    for r in top_repos:
        lines.append(f"  - {r['name']} ({r['language'] or '?'}, {r['stars']}★): {r['description'][:120]}")

    if profile_readme:
        lines.append("")
        lines.append("--- Profile README ---")
        lines.append(profile_readme)

    return {"content_text": "\n".join(lines), "content_type": "text", "metadata": meta}


def _fetch_github_repo(owner: str, repo: str, headers: dict) -> dict[str, Any]:
    import requests

    r = requests.get(f"https://api.github.com/repos/{owner}/{repo}", headers=headers, timeout=10)
    r.raise_for_status()
    data = r.json()

    meta: dict[str, Any] = {
        "full_name": data.get("full_name"),
        "stars": data.get("stargazers_count", 0),
        "forks": data.get("forks_count", 0),
        "language": data.get("language"),
        "description": data.get("description", ""),
        "topics": data.get("topics", []),
        "open_issues": data.get("open_issues_count", 0),
    }

    lines = [
        f"GitHub Repo: {data.get('full_name', f'{owner}/{repo}')}",
        f"Description: {data.get('description', 'N/A')}",
        f"Language: {data.get('language', 'N/A')} | Stars: {meta['stars']} | Forks: {meta['forks']}",
        f"Topics: {', '.join(meta['topics']) or 'N/A'}",
    ]

    # Repo languages breakdown
    try:
        langs_r = requests.get(
            f"https://api.github.com/repos/{owner}/{repo}/languages",
            headers=headers, timeout=10,
        )
        if langs_r.ok:
            lang_data = langs_r.json() or {}
            if lang_data:
                meta["languages"] = lang_data
                lines.append(f"Languages: {', '.join(lang_data.keys())}")
    except Exception:
        pass

    readme_r = requests.get(f"https://api.github.com/repos/{owner}/{repo}/readme", headers=headers, timeout=10)
    if readme_r.ok:
        import base64
        readme_data = readme_r.json()
        content_b64 = readme_data.get("content", "")
        try:
            readme_text = base64.b64decode(content_b64).decode("utf-8", errors="replace")[:6000]
            lines.append(f"\nREADME (excerpt):\n{readme_text}")
        except Exception:
            pass

    # Fetch owner profile and merge — this gives us the candidate's full
    # GitHub presence even when only a repo URL was provided.
    try:
        owner_result = _fetch_github_user(owner, headers)
        owner_meta = owner_result.get("metadata", {})
        meta["owner_profile"] = {
            k: owner_meta.get(k)
            for k in ("username", "name", "bio", "company", "location",
                       "blog", "email", "twitter_username", "hireable",
                       "public_repos", "followers", "total_stars", "languages",
                       "top_repos", "social_accounts", "organizations")
        }
        lines.append(f"\n--- Owner profile ---\n{owner_result.get('content_text', '')}")
        log.info("github    merged owner profile @%s into repo %s/%s", owner, owner, repo)
    except Exception as e:
        log.debug("github    owner profile fetch failed for %s: %s", owner, e)

    return {"content_text": "\n".join(lines), "content_type": "text", "metadata": meta}


# ---------------------------------------------------------------------------
# Cloudflare Crawl  (Browser Rendering REST API – free tier)
# ---------------------------------------------------------------------------

def fetch_cloudflare_crawl(url: str) -> dict[str, Any]:
    """Crawl a URL via Cloudflare Browser Rendering /crawl endpoint.
    Requires CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN env vars.
    Falls back to plain HTTP if Cloudflare is not configured or fails."""
    import requests

    account_id = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if not account_id or not api_token:
        log.info("cloudflare  no credentials, falling back to plain HTTP for %s", url)
        return _fallback_plain(url)

    log.info("cloudflare  crawling url=%s", url)
    base = f"https://api.cloudflare.com/client/v4/accounts/{account_id}/browser-rendering/crawl"
    headers = {"Authorization": f"Bearer {api_token}", "Content-Type": "application/json"}

    try:
        start_r = requests.post(base, headers=headers, json={
            "url": url,
            "scrapeOptions": {"formats": ["markdown"]},
            "maxPages": 3,
        }, timeout=30)
        start_r.raise_for_status()
        job = start_r.json()

        if job.get("success") and job.get("result"):
            pages = job["result"]
            md_parts = []
            meta_pages = []
            for page in pages[:3]:
                md = page.get("markdown", page.get("text", ""))
                page_url = page.get("url", url)
                md_parts.append(f"## {page_url}\n{md[:6000]}")
                meta_pages.append({"url": page_url, "title": page.get("title", "")})
            log.info("cloudflare  done, %d pages fetched for %s", len(pages), url)
            return {
                "content_text": "\n\n".join(md_parts),
                "content_type": "markdown",
                "metadata": {"pages": meta_pages, "source": "cloudflare"},
            }

        log.warning("cloudflare  no result, falling back to plain HTTP for %s", url)
        return _fallback_plain(url)
    except Exception as e:
        log.error("cloudflare  failed url=%s error=%s, falling back to plain HTTP", url, e)
        return _fallback_plain(url)


def _fallback_plain(url: str) -> dict[str, Any]:
    """Plain HTTP fetch + HTML text extraction."""
    from link_scraper import scrape_url
    log.info("plain_http  fetching url=%s", url)
    text = scrape_url(url)
    log.info("plain_http  done, content_length=%d for %s", len(text), url)
    return {"content_text": text, "content_type": "text", "metadata": {"source": "plain_http"}}


# ---------------------------------------------------------------------------
# Research Papers / PDF
# ---------------------------------------------------------------------------

def fetch_paper(url: str) -> dict[str, Any]:
    """Fetch a PDF or research paper URL and extract text."""
    import requests

    log.info("paper     fetching url=%s", url)
    try:
        parsed = urlparse(url)
        path = parsed.path.lower()

        if "arxiv.org" in (parsed.hostname or "") and "/abs/" in path:
            pdf_url = url.replace("/abs/", "/pdf/") + ".pdf"
            log.debug("paper     rewrote arxiv abstract → pdf: %s", pdf_url)
        elif "doi.org" in (parsed.hostname or ""):
            pdf_url = url
        else:
            pdf_url = url

        if not path.endswith(".pdf") and "arxiv" not in (parsed.hostname or ""):
            log.info("paper     not a PDF URL, falling back to plain HTTP for %s", url)
            return _fallback_plain(url)

        resp = requests.get(
            pdf_url,
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0 (compatible; MireloBot/1.0)"},
            allow_redirects=True,
        )
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if "pdf" in content_type:
            log.info("paper     extracting text from PDF (%d bytes)", len(resp.content))
            return _extract_pdf_text(resp.content, url)
        elif "html" in content_type:
            log.info("paper     got HTML instead of PDF, falling back to plain HTTP")
            return _fallback_plain(url)
        else:
            log.info("paper     got non-PDF content (%s), using raw text (header only)", content_type)
            return {"content_text": resp.text[:3000], "content_type": "text", "metadata": {"source": "paper_direct"}}

    except Exception as e:
        log.error("paper     failed url=%s error=%s", url, e)
        return {"content_text": f"[Paper fetch error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}


def _extract_pdf_text(pdf_bytes: bytes, url: str) -> dict[str, Any]:
    """Extract header section (authors, affiliations, abstract) from a PDF.

    Only reads the first 3 pages and caps at 3000 chars — the rest of a
    research paper (methodology, results, references) isn't useful for
    candidate evaluation.
    """
    import io
    try:
        import pdfplumber
        pages_text = []
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages[:3]:
                text = page.extract_text() or ""
                if text.strip():
                    pages_text.append(text)
        full = "\n\n".join(pages_text)[:3000]
        log.info("paper     extracted %d pages, %d chars (header only)", len(pages_text), len(full))
        return {
            "content_text": full,
            "content_type": "text",
            "metadata": {"source": "pdfplumber", "url": url, "pages_extracted": len(pages_text)},
        }
    except ImportError:
        return {"content_text": "[pdfplumber not installed]", "content_type": "text", "metadata": {}, "error": "pdfplumber not installed"}
    except Exception as e:
        return {"content_text": f"[PDF extraction error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# LinkedIn  (Datablist)
# ---------------------------------------------------------------------------

def fetch_linkedin(url: str, candidate_name: str = "") -> dict[str, Any]:
    """Fetch LinkedIn profile data via Datablist or Serper fallback."""
    log.info("linkedin  fetching url=%s", url)
    datablist_key = os.environ.get("DATABLIST_API_KEY")
    if datablist_key:
        log.info("linkedin  using Datablist API")
        return _fetch_linkedin_datablist(url, datablist_key)
    serper_key = os.environ.get("SERPER_API_KEY")
    if serper_key and candidate_name:
        log.info("linkedin  no Datablist key, falling back to Serper search for '%s'", candidate_name)
        return _fetch_linkedin_serper(candidate_name, serper_key)
    log.warning("linkedin  no Datablist or Serper key configured for %s", url)
    return {"content_text": f"[LinkedIn: no Datablist or Serper key configured for {url}]", "content_type": "text", "metadata": {"source": "none"}}


def _fetch_linkedin_datablist(url: str, api_key: str) -> dict[str, Any]:
    import requests
    log.info("linkedin  Datablist request for %s", url)
    try:
        r = requests.post(
            "https://api.datablist.com/v1/enrichments/linkedin-profile",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"url": url},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        profile = data.get("result", data)
        lines = [
            f"LinkedIn: {profile.get('name', 'N/A')}",
            f"Headline: {profile.get('headline', 'N/A')}",
            f"Location: {profile.get('location', 'N/A')}",
            f"Summary: {profile.get('summary', 'N/A')}",
        ]
        if profile.get("experience"):
            lines.append("Experience:")
            for exp in profile["experience"][:5]:
                lines.append(f"  - {exp.get('title', '')} at {exp.get('company', '')} ({exp.get('duration', '')})")
        if profile.get("education"):
            lines.append("Education:")
            for edu in profile["education"][:3]:
                lines.append(f"  - {edu.get('school', '')} – {edu.get('degree', '')}")
        log.info("linkedin  Datablist done for %s", url)
        return {
            "content_text": "\n".join(lines),
            "content_type": "text",
            "metadata": {"source": "datablist", "profile": profile},
        }
    except Exception as e:
        log.error("linkedin  Datablist failed url=%s error=%s", url, e)
        return {"content_text": f"[Datablist error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}


def _fetch_linkedin_serper(candidate_name: str, api_key: str) -> dict[str, Any]:
    """Fallback: search Serper for the candidate's LinkedIn profile snippet."""
    import requests
    log.info("linkedin  Serper search for '%s'", candidate_name)
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            json={"q": f'site:linkedin.com/in "{candidate_name}"', "num": 3},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        results = r.json().get("organic", [])
        if not results:
            log.warning("linkedin  Serper returned 0 results for '%s'", candidate_name)
            return {"content_text": "[No LinkedIn results found via Serper]", "content_type": "text", "metadata": {"source": "serper"}}
        lines = []
        for res in results[:3]:
            lines.append(f"Title: {res.get('title', '')}")
            lines.append(f"Snippet: {res.get('snippet', '')}")
            lines.append(f"URL: {res.get('link', '')}")
            lines.append("")
        log.info("linkedin  Serper done, %d results for '%s'", len(results), candidate_name)
        return {
            "content_text": "\n".join(lines),
            "content_type": "text",
            "metadata": {"source": "serper", "results": results[:3]},
        }
    except Exception as e:
        log.error("linkedin  Serper failed for '%s' error=%s", candidate_name, e)
        return {"content_text": f"[Serper LinkedIn search error: {e}]", "content_type": "text", "metadata": {}, "error": str(e)}


# ---------------------------------------------------------------------------
# Plain / Web  (default fallback)
# ---------------------------------------------------------------------------

def fetch_web(url: str) -> dict[str, Any]:
    """Default fetcher: try Cloudflare first, then plain HTTP."""
    log.info("web       fetching url=%s", url)
    cf_account = os.environ.get("CLOUDFLARE_ACCOUNT_ID")
    cf_token = os.environ.get("CLOUDFLARE_API_TOKEN")
    if cf_account and cf_token:
        return fetch_cloudflare_crawl(url)
    return _fallback_plain(url)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

_FETCHERS: dict[str, Any] = {
    "github": fetch_github,
    "linkedin": fetch_linkedin,
    "paper": fetch_paper,
    "blog": fetch_cloudflare_crawl,
    "web": fetch_web,
}


def get_fetcher(link_type: str):
    """Return the right fetcher function for a link type."""
    return _FETCHERS.get(link_type, fetch_web)
