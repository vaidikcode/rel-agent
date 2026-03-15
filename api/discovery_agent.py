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

from agent import _get_llm, _message_content_to_str

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
    log.info("search    Serper returned %d results for query", len(organic))
    return organic


def _build_search_queries(job_description: str) -> list[str]:
    llm = _get_llm()
    prompt = f"""You are a technical recruiter. Generate exactly 3 Google search queries to find
candidate profiles (people, not job listings) matching this role.
Target professional sites: LinkedIn, GitHub, StackOverflow, personal blogs, portfolios.
Each query should cover a different angle.

Job description:
---
{job_description[:5000]}
---

Return exactly 3 lines, one query per line, nothing else."""

    msg = llm.invoke([
        SystemMessage(content="You generate search queries for recruiting. Return only queries, one per line."),
        HumanMessage(content=prompt),
    ])
    content = _message_content_to_str(getattr(msg, "content", str(msg)))
    queries = [q.strip().strip('"') for q in content.strip().split("\n") if q.strip()]
    return queries[:3] or [f"candidates for {job_description[:80]}"]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def search_node(state: DiscoveryState) -> dict:
    queries = _build_search_queries(state["job_description"])
    log.info("search    generated %d queries", len(queries))
    for i, q in enumerate(queries, 1):
        log.info("search    query %d: %s", i, q[:100])
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
    return {"search_results": all_results[:25]}


def extract_node(state: DiscoveryState) -> dict:
    results = state.get("search_results", [])
    if not results:
        return {"candidates": []}

    snippets = "\n\n".join(
        f"Title: {r.get('title', '')}\nURL: {r.get('link', '')}\nSnippet: {r.get('snippet', '')}"
        for r in results[:25]
    )

    llm = _get_llm()
    prompt = f"""Extract candidate profiles from these search results for a recruiting tool.

Job context:
---
{state['job_description'][:2500]}
---

Search results:
---
{snippets[:12000]}
---

For each result that could represent a real person (developer profile, portfolio, blog, GitHub, LinkedIn, etc.), extract:
- name: full name if visible, otherwise a short label from the title
- headline: their professional title/role
- location: if mentioned, else "Unknown"
- skills: array of relevant skills (strings)
- summary: one sentence on why they might be relevant
- links: array of objects with "url" and "label". Include multiple links per candidate when available (e.g. LinkedIn, GitHub, portfolio, blog, Stack Overflow). For each person, add every relevant URL you can identify from the results (same person may appear in multiple results with different links).

Include any result that seems to belong to a real person or their work.
Return a JSON array of objects. Return ONLY the JSON array, no markdown fences."""

    msg = llm.invoke([
        SystemMessage(content="Extract structured candidate data from search results. Return only valid JSON array."),
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
