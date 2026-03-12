"""Extract candidate name and email from resume text using LLM."""
import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agent import _get_llm, _message_content_to_str

GEMINI_MODEL = "gemini-flash-latest"


def extract_candidate_details(resume_text: str) -> dict[str, str]:
    """Extract name and email from resume text. Returns { name, email }."""
    llm = _get_llm()
    prompt = f"""Extract the candidate's full name and email from this resume text. If not found, use "Unknown" for name and "" for email.

Resume text (excerpt):
---
{resume_text[:8000]}
---

Respond with exactly two lines:
NAME: <full name or Unknown>
EMAIL: <email or leave empty>"""
    msg = llm.invoke([
        SystemMessage(content="You extract structured data. Reply only with NAME: and EMAIL: lines."),
        HumanMessage(content=prompt),
    ])
    content = _message_content_to_str(getattr(msg, "content", str(msg)))
    name, email = "Unknown", ""
    for line in content.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("NAME:"):
            name = line[5:].strip() or "Unknown"
        elif line.upper().startswith("EMAIL:"):
            email = line[6:].strip()
    return {"name": name or "Unknown", "email": email}
