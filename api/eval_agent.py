"""
ReAct evaluation agent.

Uses a LangGraph tool-calling loop to let the LLM decide which candidate
URLs to fetch and when to search the web for more profiles.

Tools:
  - web_search(query)  — free Google search via Serper (no loop cost)
  - fetch_url(url)     — fetch page content (max MAX_TOOL_LOOPS successful calls)

LLM calls budget per candidate:  tool-loop iterations + 1 (eval+details).
"""
import json
import logging
from typing import Any, TypedDict

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from agent import (
    RequirementVerdict,
    _message_content_to_str,
    _parse_batched_verdicts,
    llm_invoke,
)
from link_classifier import infer_link_type
from link_fetchers import fetch_linkedin, get_fetcher

import os

log = logging.getLogger("eval_agent")

MAX_TOOL_LOOPS = 4

# ---------------------------------------------------------------------------
# Agent state
# ---------------------------------------------------------------------------

class EvalAgentState(TypedDict, total=False):
    candidate_info: str
    candidate_name: str
    candidate_id: str
    requirements: list[dict[str, Any]]
    initial_links: list[dict[str, Any]]
    # accumulated during tool loop
    context_parts: list[str]
    links_fetched: list[dict[str, Any]]
    fetched_urls: list[str]
    loop_count: int
    messages: list[Any]
    # filled after evaluation
    verdicts: dict[str, RequirementVerdict]
    evaluation_details: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Tool execution (not LLM — just HTTP fetchers)
# ---------------------------------------------------------------------------

def _run_fetch_tool(url: str, link_type: str, candidate_name: str) -> dict[str, Any]:
    """Execute the appropriate fetcher for a URL. Returns fetcher result dict."""
    if link_type == "linkedin":
        return fetch_linkedin(url, candidate_name=candidate_name)
    fetcher = get_fetcher(link_type)
    return fetcher(url)


def _run_web_search(query: str) -> dict[str, Any]:
    """Execute a Google search via Serper and return formatted results."""
    import requests

    api_key = os.environ.get("SERPER_API_KEY")
    if not api_key:
        return {"results": [], "error": "SERPER_API_KEY not set"}

    log.info("react     web_search query='%s'", query[:80])
    try:
        r = requests.post(
            "https://google.serper.dev/search",
            json={"q": query, "num": 8},
            headers={"X-API-KEY": api_key, "Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        organic = r.json().get("organic", [])
        log.info("react     web_search got %d results", len(organic))

        lines = []
        for res in organic[:8]:
            lines.append(f"Title: {res.get('title', '')}")
            lines.append(f"URL: {res.get('link', '')}")
            lines.append(f"Snippet: {res.get('snippet', '')}")
            lines.append("")
        return {"results": organic[:8], "text": "\n".join(lines)}
    except Exception as e:
        log.error("react     web_search failed: %s", e)
        return {"results": [], "error": str(e)}


# ---------------------------------------------------------------------------
# Tool schemas
# ---------------------------------------------------------------------------

_FETCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "fetch_url",
        "description": (
            "Fetch content from a URL. Use to gather more information about the candidate. "
            "The site type is auto-detected."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch"},
                "link_type": {
                    "type": "string",
                    "enum": ["github", "linkedin", "paper", "blog", "web"],
                    "description": "Type of site (auto-detected, but provide your best guess)",
                },
            },
            "required": ["url", "link_type"],
        },
    },
}

_SEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search Google for information about the candidate. "
            "Returns titles, URLs, and snippets. Use to discover GitHub, LinkedIn, "
            "personal websites, or Google Scholar profiles when you don't have direct links."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Google search query (e.g. '\"Alice Smith\" site:github.com')",
                },
            },
            "required": ["query"],
        },
    },
}


def _build_system_prompt(requirements: list[dict[str, Any]]) -> str:
    req_labels = ", ".join(r.get("label", r["id"]) for r in requirements)
    return f"""You are a candidate research agent. Your goal is to gather enough information
about a candidate to evaluate them against these requirements: {req_labels}.

You have TWO tools:
1. **web_search(query)** — Search Google. Returns titles, URLs, and snippets. Use this to
   discover the candidate's GitHub, LinkedIn, personal website, or Google Scholar page.
   web_search calls are FREE and do not count against your fetch budget.
2. **fetch_url(url, link_type)** — Fetch full content from a URL. The site type is
   auto-detected. You have at most {MAX_TOOL_LOOPS} successful fetch_url calls.

STRATEGY:
1. If the known links already include a GitHub or LinkedIn URL, fetch those first.
2. If the known links are thin (only a paper, or only 1 link), start with a web_search
   to discover more profiles: e.g. web_search('"Candidate Name" site:github.com OR site:linkedin.com').
3. After each fetch, read the returned content for new URLs (websites in GitHub bios,
   GitHub links on LinkedIn, author homepages on papers). Fetch discovered URLs next.
4. If you still need more info and have budget left, do another targeted web_search.
5. When you have enough information or run out of fetch calls, respond with DONE.

RULES for fetch_url:
- Do NOT guess or construct URLs without evidence. Use web_search to find them first.
- OK: You found "https://alice.dev" in a GitHub bio → fetch it.
- NOT OK: Guess "github.com/alicesmith" from the candidate's name → use web_search instead.
- Failed fetches (404s, errors) do NOT count against your budget, but waste time.

RULES for web_search:
- Keep queries short and specific. Include the candidate's name in quotes.
- Add 1-2 disambiguating keywords you already know (university, field, company).
- Good: '"Alice Smith" MIT computer vision site:github.com'
- Good: '"Alice Smith" machine learning researcher'
- You can call web_search multiple times if needed — it's free.

IDENTITY VERIFICATION (important):
Search results may return a different person with the same name. After fetching a
URL found via web_search, check that the content matches YOUR candidate:
- Same institution, research area, skills, location, or other known facts.
- If the fetched content is clearly about a different person (different field,
  different country, different career), IGNORE that content entirely — do not use
  it for evaluation. Note briefly: "Content discarded — different person."
- Links found WITHIN already-verified content (e.g. a website URL in a GitHub bio)
  are trusted and do not need extra verification.

Site-specific notes:
- LinkedIn: you'll only get search snippets (no full profile). Still useful for headlines.
- GitHub: returns profile, repos, languages, README, social links. Very rich.
- Papers / arxiv: fetch ONE page only (abstract). Don't follow links within papers.
- Portfolios / blogs / github.io: fetch the landing page only.

When done, respond with exactly DONE (no tool calls)."""


def _build_initial_user_msg(
    candidate_info: str,
    links: list[dict[str, Any]],
) -> str:
    link_lines = "\n".join(
        f"  - [{l.get('link_type', 'web')}] {l.get('label', l.get('url', ''))} → {l.get('url', '')}"
        for l in links
    ) or "  (none)"
    return f"""Here is the candidate's profile and known links:

{candidate_info}

Known links:
{link_lines}

Start by fetching the most informative known link. After each fetch, carefully read the
returned content for new URLs (websites in GitHub bios, GitHub links on LinkedIn, etc.)
and fetch those discovered URLs next. Only construct a URL if you see an exact username
or link reference in the content."""


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def init_node(state: EvalAgentState) -> dict:
    """Seed the message history and zero out counters."""
    system = _build_system_prompt(state["requirements"])
    user = _build_initial_user_msg(state["candidate_info"], state["initial_links"])
    return {
        "messages": [
            SystemMessage(content=system),
            HumanMessage(content=user),
        ],
        "context_parts": [state["candidate_info"]],
        "links_fetched": [],
        "fetched_urls": [],
        "loop_count": 0,
        "verdicts": {},
        "evaluation_details": None,
    }


def react_node(state: EvalAgentState) -> dict:
    """Call the LLM with tool definitions. It either makes tool calls or says DONE."""
    from langchain_google_genai import ChatGoogleGenerativeAI
    from agent import _current_key, _load_keys, _KEY_POOL, GEMINI_MODEL

    if not _KEY_POOL:
        _load_keys()

    llm = ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=_current_key(),
        temperature=0.1,
        max_retries=0,
    )
    llm_with_tools = llm.bind_tools([
        _FETCH_TOOL_SCHEMA["function"],
        _SEARCH_TOOL_SCHEMA["function"],
    ])

    msg = llm_with_tools.invoke(state["messages"])
    return {"messages": state["messages"] + [msg]}


def tool_executor_node(state: EvalAgentState) -> dict:
    """Execute any tool calls from the last AI message and append results."""
    messages = list(state["messages"])
    last_msg = messages[-1]
    context_parts = list(state.get("context_parts", []))
    links_fetched = list(state.get("links_fetched", []))
    fetched_urls = set(state.get("fetched_urls", []))
    loop_count = state.get("loop_count", 0)
    candidate_name = state.get("candidate_name", "")

    tool_calls = getattr(last_msg, "tool_calls", None) or []
    for tc in tool_calls:
        args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
        tc_id = tc.get("id", "") if isinstance(tc, dict) else getattr(tc, "id", "")
        tool_name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")

        # ── web_search (free, no loop budget) ──
        if tool_name == "web_search":
            query = args.get("query", "").strip()
            if not query:
                messages.append(ToolMessage(content="Empty search query.", tool_call_id=tc_id))
                continue
            result = _run_web_search(query)
            if result.get("error"):
                messages.append(ToolMessage(
                    content=f"Search error: {result['error']}",
                    tool_call_id=tc_id,
                ))
            else:
                messages.append(ToolMessage(
                    content=result.get("text", "No results.")[:4000],
                    tool_call_id=tc_id,
                ))
            continue

        # ── fetch_url (costs 1 loop) ──
        url = args.get("url", "").strip()

        if not url or url in fetched_urls:
            messages.append(ToolMessage(
                content="Already fetched or invalid URL.",
                tool_call_id=tc_id,
            ))
            continue

        link_type = infer_link_type(url)

        log.info("react     loop=%d fetching [%s] %s", loop_count + 1, link_type, url[:80])
        try:
            result = _run_fetch_tool(url, link_type, candidate_name)
            content_text = result.get("content_text", "")[:8000]
            error = result.get("error")
        except Exception as e:
            content_text = f"[Fetch error: {e}]"
            error = str(e)

        fetched_urls.add(url)

        if error:
            messages.append(ToolMessage(
                content=f"Error fetching {url}: {error}. This did NOT count against your tool budget. You still have {MAX_TOOL_LOOPS - loop_count} calls left.",
                tool_call_id=tc_id,
            ))
            log.warning("react     fetch failed (not counted): %s — %s", url[:60], error)
            continue

        context_parts.append(f"--- [{link_type}] {url} ---\n{content_text[:6000]}")
        links_fetched.append({
            "url": url,
            "link_type": link_type,
            "content_text": content_text,
            "content_type": result.get("content_type", "text"),
            "metadata": result.get("metadata", {}),
        })
        loop_count += 1

        messages.append(ToolMessage(
            content=content_text[:4000],
            tool_call_id=tc_id,
        ))
        log.info("react     fetched %d chars from %s", len(content_text), url[:60])

    return {
        "messages": messages,
        "context_parts": context_parts,
        "links_fetched": links_fetched,
        "fetched_urls": list(fetched_urls),
        "loop_count": loop_count,
    }


def should_continue(state: EvalAgentState) -> str:
    """Route: if LLM made tool calls and we haven't hit the cap, execute tools.
    Otherwise go to evaluation."""
    messages = state.get("messages", [])
    loop_count = state.get("loop_count", 0)

    if loop_count >= MAX_TOOL_LOOPS:
        log.info("react     hit max %d loops, moving to evaluation", MAX_TOOL_LOOPS)
        return "evaluate"

    if messages:
        last = messages[-1]
        tool_calls = getattr(last, "tool_calls", None) or []
        if tool_calls:
            return "tools"

    return "evaluate"


def evaluate_node(state: EvalAgentState) -> dict:
    """Single LLM call: evaluate all requirements + extract structured details."""
    requirements = state["requirements"]
    context_parts = state.get("context_parts", [])
    candidate_text = "\n\n".join(context_parts)[:16000]

    req_block = "\n\n".join(
        f'- id: "{r["id"]}"\n  label: {r.get("label", r["id"])}\n  what to check: {r.get("prompt", "")}'
        for r in requirements
    )

    prompt = f"""You have gathered information about a candidate. Now do TWO things in one response.

Candidate information:
---
{candidate_text}
---

IMPORTANT: Some content above may have been fetched via web search and could belong to
a different person with the same name. Only use information that is clearly about this
specific candidate. Ignore anything that doesn't match (different field, institution, etc.).

TASK 1 — EVALUATE against each requirement.
Requirements:
{req_block}

TASK 2 — EXTRACT structured details about the candidate.

Return a single JSON object (no markdown fences, no extra text) with exactly these keys:
- "evaluations": array of objects, one per requirement, each with:
    - "requirement_id": exact id string
    - "passed": true or false
    - "reason": one short sentence
- "experience_summary": string (2-4 sentences on work history)
- "education": string (degrees/institutions, or "Not mentioned")
- "key_skills_evidence": string (concrete evidence for top skills)
- "strengths": array of strings (3-6 bullet points)
- "concerns": array of strings (0-4 bullet points, empty array if none)
- "fit_summary": string (2-3 sentences overall fit)

Return ONLY valid JSON."""

    msg = llm_invoke([
        SystemMessage(content="You are a strict but fair candidate evaluator and analyst. Output only valid JSON."),
        HumanMessage(content=prompt),
    ])
    raw = _message_content_to_str(msg.content if hasattr(msg, "content") else str(msg)).strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    verdicts: dict[str, RequirementVerdict] = {}
    for r in requirements:
        verdicts[r["id"]] = {"passed": False, "reason": "Not evaluated"}

    evaluation_details: dict[str, Any] = {}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        log.warning("evaluate  failed to parse combined JSON, falling back")
        data = {}

    evals_arr = data.get("evaluations", [])
    if isinstance(evals_arr, list):
        for item in evals_arr:
            if not isinstance(item, dict):
                continue
            rid = item.get("requirement_id")
            if rid not in verdicts:
                continue
            passed = item.get("passed", False)
            if isinstance(passed, str):
                passed = passed.strip().upper() in ("TRUE", "YES", "1")
            reason = (item.get("reason") or "").strip() or "No reason given"
            verdicts[rid] = {"passed": bool(passed), "reason": reason}

    for key in ("experience_summary", "education", "key_skills_evidence", "fit_summary"):
        val = data.get(key)
        evaluation_details[key] = (str(val).strip() if val else None) or None
    for key in ("strengths", "concerns"):
        val = data.get(key)
        if isinstance(val, list):
            evaluation_details[key] = [str(s).strip() for s in val if s][:8]
        else:
            evaluation_details[key] = []

    log.info("evaluate  verdicts: %d/%d passed",
             sum(1 for v in verdicts.values() if v["passed"]), len(verdicts))
    return {"verdicts": verdicts, "evaluation_details": evaluation_details}


# ---------------------------------------------------------------------------
# Build graph
# ---------------------------------------------------------------------------

def build_eval_graph() -> Any:
    workflow = StateGraph(EvalAgentState)

    workflow.add_node("init", init_node)
    workflow.add_node("react", react_node)
    workflow.add_node("tools", tool_executor_node)
    workflow.add_node("evaluate", evaluate_node)

    workflow.add_edge(START, "init")
    workflow.add_edge("init", "react")
    workflow.add_conditional_edges("react", should_continue, {"tools": "tools", "evaluate": "evaluate"})
    workflow.add_edge("tools", "react")
    workflow.add_edge("evaluate", END)

    return workflow.compile()


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_eval_agent(
    candidate_info: str,
    candidate_name: str,
    candidate_id: str,
    initial_links: list[dict[str, Any]],
    requirements: list[dict[str, Any]],
) -> dict[str, Any]:
    """Run the ReAct evaluation agent.

    Returns dict with keys:
        verdicts        – {requirement_id: {passed, reason}}
        evaluation_details – structured details dict
        links_fetched   – list of {url, link_type, content_text, metadata, ...}
    """
    graph = build_eval_graph()
    initial_state: EvalAgentState = {
        "candidate_info": candidate_info,
        "candidate_name": candidate_name,
        "candidate_id": candidate_id,
        "requirements": requirements,
        "initial_links": initial_links,
        "context_parts": [],
        "links_fetched": [],
        "fetched_urls": [],
        "loop_count": 0,
        "messages": [],
        "verdicts": {},
        "evaluation_details": None,
    }
    result = graph.invoke(initial_state)
    return {
        "verdicts": result.get("verdicts", {}),
        "evaluation_details": result.get("evaluation_details"),
        "links_fetched": result.get("links_fetched", []),
    }
