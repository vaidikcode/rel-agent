"""
Discovery agent: search the web for candidates matching a job description.
Focus: find people and extract their info + multiple links. No requirements, no scoring.

Nodes:
  1. search  – Build queries from job description only, call Serper
  2. extract – Use Gemini to pull structured profiles + multiple links per candidate
"""
import json
import logging
import os
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph

from agent import llm_invoke, _message_content_to_str

log = logging.getLogger("discovery")


class DiscoveredCandidate(TypedDict, total=False):
    name: str
    headline: str
    location: str
    skills: list[str]
    summary: str
    links: list[dict]


class DiscoveryState(TypedDict, total=False):
    job_description: str
    search_results: list[dict]
    candidates: list[DiscoveredCandidate]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serper_search(query: str, num_results: int = 10) -> list[dict]:
    import requests
    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        raise RuntimeError("SERPER_API_KEY must be set")
    resp = requests.post(
        "https://google.serper.dev/search",
        json={"q": query, "num": num_results},
        headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    organic = data.get("organic") or []
    log.info("search    Serper q='%s' → %d results", query, len(organic))
    return organic


def _extract_job_summary_and_queries(job_description: str) -> tuple[dict[str, Any], list[str]]:
    """Single LLM call: extract job summary (role, skills, domain) and 5-6 search queries."""
    prompt = f"""Use this job description to do two things in one response.

Job description:
{job_description[:2500]}

Return a single JSON object with exactly these keys (no other text, no markdown):
1. "role_title": exact job title or role (e.g. "Senior ML Engineer", "Research Scientist")
2. "key_skills": array of 3-5 concrete skills/tech (e.g. ["Python", "PyTorch", "NLP"])
3. "domain": one phrase for industry/focus (e.g. "machine learning", "backend infrastructure")
4. "search_queries": array of 5-6 Google search query strings to find people matching this role.

Rules for search_queries:
- Each query must use site: (e.g. site:linkedin.com/in, site:github.com, site:arxiv.org).
- Include role or 1-2 key skills per query. No boolean (OR/AND). Under 10-12 words each.
- Cover: 1-2 LinkedIn, 1-2 GitHub, 1 arxiv/scholar, 1 general. Vary phrasing.

Example search_queries entry: "site:linkedin.com/in Senior ML Engineer Python"
Return only valid JSON."""

    msg = llm_invoke([
        SystemMessage(content="You extract structured data. Return only a JSON object, no markdown."),
        HumanMessage(content=prompt),
    ])
    content = _message_content_to_str(getattr(msg, "content", str(msg))).strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    try:
        data = json.loads(content)
        role = (data.get("role_title") or "").strip() or None
        skills = data.get("key_skills")
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        if not isinstance(skills, list):
            skills = []
        skills = [str(s).strip() for s in skills[:6] if s]
        domain = (data.get("domain") or "").strip() or None
        summary = {"role_title": role, "key_skills": skills, "domain": domain}
        raw_queries = data.get("search_queries")
        if isinstance(raw_queries, list):
            queries = [str(q).strip().strip('"') for q in raw_queries if q][:6]
        else:
            queries = []
        if not queries:
            queries = [f"site:linkedin.com/in {job_description[:60]}"]
        return summary, queries
    except (json.JSONDecodeError, TypeError):
        summary = {"role_title": None, "key_skills": [], "domain": None}
        return summary, [f"site:linkedin.com/in {job_description[:80]}"]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def search_node(state: DiscoveryState) -> dict:
    job_description = state["job_description"] or ""
    job_summary, queries = _extract_job_summary_and_queries(job_description)
    log.info("search    summary role=%r skills=%s domain=%r", job_summary.get("role_title"), job_summary.get("key_skills"), job_summary.get("domain"))
    log.info("search    generated %d queries", len(queries))
    for i, q in enumerate(queries, 1):
        log.info("search    query %d: %s", i, q)
    all_results: list[dict] = []
    seen_urls: set[str] = set()
    for q in queries:
        try:
            results = _serper_search(q, num_results=10)
            for r in results:
                url = r.get("link", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(r)
        except Exception as e:
            log.error("search    Serper failed for query '%s': %s", q[:60], e)
    log.info("search    %d unique results from %d queries", len(all_results), len(queries))
    return {"search_results": all_results[:45]}


def extract_node(state: DiscoveryState) -> dict:
    results = state.get("search_results", [])
    if not results:
        return {"candidates": []}

    snippets = "\n\n".join(
        f"Title: {r.get('title', '')}\nURL: {r.get('link', '')}\nSnippet: {r.get('snippet', '')}"
        for r in results[:45]
    )

    prompt = f"""Extract people from these search results.

Job: {state['job_description'][:1500]}

Results:
{snippets[:12000]}

For each real person found, return JSON with:
- name, headline, location ("Unknown" if missing), skills (array), summary (1 sentence)
- links: array of {{"url","label"}}. Include every URL for the person (LinkedIn, GitHub, arxiv papers, portfolio, scholar page, etc.). For papers, use the first author name and include the paper URL.

Merge the same person across results. Return ONLY a JSON array."""

    msg = llm_invoke([
        SystemMessage(content="Extract candidate profiles as JSON array. Include researchers from papers."),
        HumanMessage(content=prompt),
    ])
    content = _message_content_to_str(getattr(msg, "content", str(msg))).strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    try:
        raw = json.loads(content)
        if not isinstance(raw, list):
            raw = []
    except json.JSONDecodeError:
        log.warning("extract   invalid JSON from LLM, falling back to empty list")
        raw = []

    candidates: list[DiscoveredCandidate] = []
    for c in raw:
        if not isinstance(c, dict):
            continue
        skills = c.get("skills", [])
        if isinstance(skills, str):
            skills = [s.strip() for s in skills.split(",") if s.strip()]
        links = c.get("links", [])
        if isinstance(links, str):
            links = [{"url": links, "label": "Profile"}]
        if not isinstance(links, list):
            links = []
        normalized_links = []
        for lnk in links:
            if isinstance(lnk, str):
                normalized_links.append({"url": lnk, "label": "Link"})
            elif isinstance(lnk, dict) and lnk.get("url"):
                normalized_links.append({"url": lnk["url"], "label": lnk.get("label", "Link")})
        candidates.append({
            "name": c.get("name", "Unknown"),
            "headline": c.get("headline", ""),
            "location": c.get("location", "Unknown"),
            "skills": skills,
            "summary": c.get("summary", ""),
            "links": normalized_links,
        })

    if not candidates and results:
        log.warning("extract   LLM returned 0 candidates, building fallback from %d results", len(results))
        for r in results[:15]:
            title = (r.get("title") or "").strip()
            link = (r.get("link") or "").strip()
            snippet = (r.get("snippet") or "").strip()
            if title or snippet:
                candidates.append({
                    "name": title.split(" - ")[0].strip()[:60] if title else "Unknown",
                    "headline": title or snippet[:80],
                    "location": "Unknown",
                    "skills": [],
                    "summary": snippet[:300] if snippet else title,
                    "links": [{"url": link, "label": "Source"}] if link else [],
                })

    log.info("extract   extracted %d candidates", len(candidates))
    for c in candidates:
        log.info("extract   candidate: %s (%d links)", c.get("name", "?"), len(c.get("links", [])))
    return {"candidates": candidates}


# ---------------------------------------------------------------------------
# Build & run
# ---------------------------------------------------------------------------

def build_discovery_graph() -> Any:
    workflow = StateGraph(DiscoveryState)
    workflow.add_node("search", search_node)
    workflow.add_node("extract", extract_node)
    workflow.add_edge(START, "search")
    workflow.add_edge("search", "extract")
    workflow.add_edge("extract", END)
    return workflow.compile()


def run_discovery(job_description: str) -> list[DiscoveredCandidate]:
    """Run search + extract and return discovered candidates with links. Does not use bucket requirements."""
    graph = build_discovery_graph()
    initial: DiscoveryState = {
        "job_description": job_description,
        "search_results": [],
        "candidates": [],
    }
    result = graph.invoke(initial)
    return result.get("candidates", [])
