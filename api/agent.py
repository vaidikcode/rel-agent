"""
LangGraph agent: one node per requirement.
Each node uses Gemini to evaluate the candidate (resume text) against that requirement and returns pass/fail + reason.
Requirements are loaded from DB (Supabase) when available, else from requirements_spec.
"""
import os
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from requirements_spec import REQUIREMENTS as FALLBACK_REQUIREMENTS

# Use exactly this model name as requested
GEMINI_MODEL = "gemini-flash-latest"


class RequirementVerdict(TypedDict):
    passed: bool
    reason: str


class AgentState(TypedDict):
    resume_text: str
    results: dict[str, RequirementVerdict]


def _get_llm():
    api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY must be set")
    return ChatGoogleGenerativeAI(
        model=GEMINI_MODEL,
        google_api_key=api_key,
        temperature=0.1,
    )


def _eval_prompt(requirement_label: str, requirement_prompt: str, resume_text: str) -> str:
    return f"""You are evaluating a candidate's resume against a specific requirement.

Requirement: {requirement_label}
What to check: {requirement_prompt}

Resume text (excerpt may be truncated):
---
{resume_text[:12000]}
---

Respond with exactly two lines:
1. VERDICT: YES or NO
2. REASON: one short sentence explaining why."""


def _message_content_to_str(content: str | list) -> str:
    """Normalize LLM message content to string (Gemini may return list of parts)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            (c.get("text", c) if isinstance(c, dict) else str(c)) for c in content
        )
    return str(content)


def _parse_verdict(response_text: str) -> RequirementVerdict:
    if not isinstance(response_text, str):
        response_text = _message_content_to_str(response_text)
    passed = False
    reason = response_text.strip()
    for line in response_text.strip().split("\n"):
        line = line.strip().upper()
        if line.startswith("VERDICT:"):
            passed = "YES" in line
        elif line.startswith("REASON:"):
            reason = line.replace("REASON:", "").strip()
    return {"passed": passed, "reason": reason or response_text[:200]}


def make_requirement_node(requirement_id: str, label: str, prompt: str):
    def node(state: AgentState) -> dict:
        llm = _get_llm()
        text = _eval_prompt(label, prompt, state["resume_text"])
        msg = llm.invoke([SystemMessage(content="You are a strict but fair resume evaluator. Answer only with VERDICT and REASON."), HumanMessage(content=text)])
        content = msg.content if hasattr(msg, "content") else str(msg)
        verdict = _parse_verdict(_message_content_to_str(content))
        new_results = dict(state["results"])
        new_results[requirement_id] = verdict
        return {"results": new_results}
    return node


def _get_requirements() -> list[dict[str, Any]]:
    try:
        from supabase_client import get_requirements as db_requirements
        return db_requirements()
    except Exception:
        return FALLBACK_REQUIREMENTS


def build_graph(requirements: list[dict[str, Any]] | None = None) -> StateGraph:
    reqs = requirements if requirements is not None else _get_requirements()
    if not reqs:
        reqs = FALLBACK_REQUIREMENTS
    workflow = StateGraph(AgentState)
    for r in reqs:
        rid = r["id"]
        label = r["label"]
        prompt = r.get("prompt", "")
        workflow.add_node(rid, make_requirement_node(rid, label, prompt))
    workflow.add_edge(START, reqs[0]["id"])
    for i in range(len(reqs) - 1):
        workflow.add_edge(reqs[i]["id"], reqs[i + 1]["id"])
    workflow.add_edge(reqs[-1]["id"], END)
    return workflow.compile()


def run_evaluation(resume_text: str, requirements: list[dict[str, Any]] | None = None) -> dict[str, RequirementVerdict]:
    graph = build_graph(requirements)
    initial: AgentState = {"resume_text": resume_text, "results": {}}
    final = graph.invoke(initial)
    return final["results"]
