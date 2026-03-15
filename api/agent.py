"""
LangGraph evaluation agent.
Evaluates a candidate against bucket requirements using scraped link content.
"""
import os
from typing import Any, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph

GEMINI_MODEL = "gemini-flash-latest"


class RequirementVerdict(TypedDict):
    passed: bool
    reason: str


class AgentState(TypedDict):
    candidate_text: str
    requirements: list[dict]
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


def _message_content_to_str(content: str | list) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            (c.get("text", c) if isinstance(c, dict) else str(c)) for c in content
        )
    return str(content)


def _eval_prompt(requirement_label: str, requirement_prompt: str, candidate_text: str) -> str:
    return f"""You are evaluating a candidate against a specific requirement.

Requirement: {requirement_label}
What to check: {requirement_prompt}

Candidate information (scraped from their online profiles):
---
{candidate_text[:12000]}
---

Respond with exactly two lines:
1. VERDICT: YES or NO
2. REASON: one short sentence explaining why."""


def _parse_verdict(response_text: str) -> RequirementVerdict:
    if not isinstance(response_text, str):
        response_text = _message_content_to_str(response_text)
    passed = False
    reason = response_text.strip()
    for line in response_text.strip().split("\n"):
        upper = line.strip().upper()
        if upper.startswith("VERDICT:"):
            passed = "YES" in upper
        elif upper.startswith("REASON:"):
            reason = line.strip()[7:].strip()
    return {"passed": passed, "reason": reason or response_text[:200]}


def make_requirement_node(requirement_id: str, label: str, prompt: str):
    def node(state: AgentState) -> dict:
        llm = _get_llm()
        text = _eval_prompt(label, prompt, state["candidate_text"])
        msg = llm.invoke([
            SystemMessage(content="You are a strict but fair candidate evaluator. Answer only with VERDICT and REASON."),
            HumanMessage(content=text),
        ])
        content = msg.content if hasattr(msg, "content") else str(msg)
        verdict = _parse_verdict(_message_content_to_str(content))
        new_results = dict(state["results"])
        new_results[requirement_id] = verdict
        return {"results": new_results}
    return node


def build_graph(requirements: list[dict[str, Any]]) -> Any:
    if not requirements:
        raise ValueError("At least one requirement is needed for evaluation")
    workflow = StateGraph(AgentState)
    for r in requirements:
        rid = r["id"]
        workflow.add_node(rid, make_requirement_node(rid, r["label"], r.get("prompt", "")))
    workflow.add_edge(START, requirements[0]["id"])
    for i in range(len(requirements) - 1):
        workflow.add_edge(requirements[i]["id"], requirements[i + 1]["id"])
    workflow.add_edge(requirements[-1]["id"], END)
    return workflow.compile()


def run_candidate_evaluation(candidate_text: str, requirements: list[dict[str, Any]]) -> dict[str, RequirementVerdict]:
    """Evaluate a candidate's scraped content against a list of requirements.
    Returns { requirement_id: { passed, reason } }."""
    graph = build_graph(requirements)
    initial: AgentState = {"candidate_text": candidate_text, "requirements": requirements, "results": {}}
    final = graph.invoke(initial)
    return final["results"]
