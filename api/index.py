"""
FastAPI app wrapping the LangGraph agent and candidate/ranking APIs.
Vercel: expose this as the serverless entrypoint (e.g. api/index.py -> /api).
"""
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

# Load .env from project root (parent of api/) when running from api/
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agent import run_evaluation
from extract_candidate import extract_candidate_details
from resume_parser import extract_resume_text
from supabase_client import (
    get_supabase,
    get_requirements,
    get_candidate_evaluations,
    insert_candidate,
    insert_evaluations,
    upload_resume,
    update_candidate_resume_url,
    get_candidates_with_scores,
    get_candidates_list,
    update_candidate,
    delete_candidate,
    create_requirement,
    update_requirement,
    delete_requirement,
)

app = FastAPI(title="Candidate Requirement Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/api")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "candidate-requirement-agent"}


def _get_requirements_fallback() -> list[dict[str, Any]]:
    try:
        return get_requirements()
    except Exception:
        from requirements_spec import REQUIREMENTS as R
        return [{"id": r["id"], "label": r["label"], "prompt": r["prompt"], "weight": 1, "sort_order": i} for i, r in enumerate(R)]


def _is_quota_error(e: BaseException) -> bool:
    msg = (getattr(e, "message", "") or str(e)).upper()
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg or "RATE" in msg


@app.post("/api/evaluate")
async def evaluate(
    file: UploadFile = File(...),
    save_to_db: bool = Form(True),
) -> dict[str, Any]:
    """Extract text from resume, extract name/email from content, run LangGraph agent, return verdict per requirement."""
    if not file.filename:
        raise HTTPException(400, "No file uploaded")
    content = await file.read()
    try:
        resume_text = extract_resume_text(content, file.filename)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if not resume_text or len(resume_text.strip()) < 50:
        raise HTTPException(400, "Could not extract enough text from the resume. Use a PDF or DOCX with selectable text.")

    reqs = _get_requirements_fallback()
    weight_by_id = {r["id"]: r.get("weight", 1) for r in reqs}

    try:
        details = extract_candidate_details(resume_text)
    except Exception as e:
        if _is_quota_error(e):
            raise HTTPException(
                429,
                "API quota or rate limit reached. Please wait a minute and try again, or check your Gemini API plan and billing.",
            ) from e
        raise

    name = (details.get("name") or "Unknown").strip()
    email = (details.get("email") or "").strip()

    try:
        results = run_evaluation(resume_text, reqs)
    except Exception as e:
        if _is_quota_error(e):
            raise HTTPException(
                429,
                "API quota or rate limit reached. Please wait a minute and try again, or check your Gemini API plan and billing.",
            ) from e
        raise

    score = sum(weight_by_id.get(rid, 1) for rid, v in results.items() if v.get("passed"))
    max_score = sum(weight_by_id.get(r["id"], 1) for r in reqs)
    relevance_percentage = round((score / max_score) * 100) if max_score else 0

    out = {
        "name": name,
        "email": email,
        "results": results,
        "score": score,
        "max_score": max_score,
        "relevance_percentage": relevance_percentage,
    }

    if save_to_db and os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        try:
            row = insert_candidate(name, email, resume_text)
            insert_evaluations(row["id"], results)
            out["candidate_id"] = row["id"]
            try:
                url = upload_resume(row["id"], file.filename or "resume.pdf", content)
                update_candidate_resume_url(row["id"], url)
            except Exception as e:
                out["save_error"] = str(e)
        except Exception as e:
            out["save_error"] = str(e)

    return out


@app.get("/api/requirements")
def list_requirements() -> list[dict[str, Any]]:
    """Return requirement id, label, prompt, weight for UI."""
    reqs = _get_requirements_fallback()
    return [{"id": r["id"], "label": r["label"], "prompt": r.get("prompt", ""), "weight": r.get("weight", 1), "sort_order": r.get("sort_order", 0)} for r in reqs]


@app.get("/api/candidates/{candidate_id}/evaluations")
def candidate_evaluations(candidate_id: str) -> list[dict[str, Any]]:
    """Return requirement verdicts (with reason) for a candidate."""
    try:
        return get_candidate_evaluations(candidate_id)
    except Exception as e:
        raise HTTPException(500, str(e))


class RequirementCreate(BaseModel):
    id: str
    label: str
    prompt: str
    weight: int = 1


class RequirementUpdate(BaseModel):
    label: str | None = None
    prompt: str | None = None
    weight: int | None = None


@app.post("/api/requirements")
def add_requirement(body: RequirementCreate) -> dict[str, Any]:
    """Add a requirement."""
    id_ = body.id.strip().lower().replace(" ", "_")
    if not id_ or not body.label or not body.prompt:
        raise HTTPException(400, "id, label, and prompt required")
    try:
        return create_requirement(id_, body.label, body.prompt, body.weight)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.patch("/api/requirements/{requirement_id}")
def patch_requirement(requirement_id: str, body: RequirementUpdate) -> dict[str, Any]:
    """Update a requirement. Body: { label?, prompt?, weight? }."""
    try:
        return update_requirement(
            requirement_id,
            label=body.label,
            prompt=body.prompt,
            weight=body.weight,
        )
    except RuntimeError:
        raise HTTPException(404, "Requirement not found")
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/requirements/{requirement_id}")
def remove_requirement(requirement_id: str) -> None:
    try:
        delete_requirement(requirement_id)
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/ranking")
def ranking() -> list[dict[str, Any]]:
    """Return candidates with total score, sorted by score descending."""
    try:
        return get_candidates_with_scores()
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/candidates")
def list_candidates() -> list[dict[str, Any]]:
    """List all candidates (admin)."""
    try:
        return get_candidates_list()
    except Exception as e:
        raise HTTPException(500, str(e))


class CandidateUpdate(BaseModel):
    name: str | None = None
    email: str | None = None


@app.patch("/api/candidates/{candidate_id}")
def patch_candidate(candidate_id: str, body: CandidateUpdate) -> dict[str, Any]:
    """Update candidate name/email (admin)."""
    try:
        return update_candidate(candidate_id, name=body.name, email=body.email)
    except RuntimeError:
        raise HTTPException(404, "Candidate not found")
    except ValueError:
        raise HTTPException(400, "Provide name and/or email")
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/candidates/{candidate_id}")
def remove_candidate(candidate_id: str) -> None:
    """Delete candidate and related evaluations (admin)."""
    try:
        delete_candidate(candidate_id)
    except Exception as e:
        raise HTTPException(500, str(e))
