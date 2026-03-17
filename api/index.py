"""
FastAPI app – Job Bucket model.
Vercel serverless entrypoint: api/index.py -> /api
"""
import logging
import os
import sys
from pathlib import Path
from typing import Any

_api_dir = Path(__file__).resolve().parent
if str(_api_dir) not in sys.path:
    sys.path.insert(0, str(_api_dir))

from dotenv import load_dotenv
load_dotenv(_api_dir.parent / ".env")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(name)-22s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("api")

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from discovery_agent import run_discovery
from eval_agent import run_eval_agent
from supabase_client import (
    list_buckets, get_bucket, create_bucket, update_bucket, delete_bucket,
    list_bucket_requirements, create_bucket_requirement, update_bucket_requirement, delete_bucket_requirement,
    list_bucket_candidates, get_bucket_candidate, insert_bucket_candidate, update_bucket_candidate, delete_bucket_candidate,
    list_candidate_links, ensure_candidate_link,
    insert_candidate_evaluations, update_candidate_evaluation_status, get_candidate_evaluations,
    upsert_link_fetch,
)

app = FastAPI(title="Mirelo AI – Job Bucket API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def _is_quota_error(e: BaseException) -> bool:
    msg = (getattr(e, "message", "") or str(e)).upper()
    return "429" in msg or "RESOURCE_EXHAUSTED" in msg or "QUOTA" in msg or "RATE" in msg


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/")
@app.get("/api")
def root():
    return {"status": "ok", "service": "mirelo-job-bucket-api"}


# ---------------------------------------------------------------------------
# Buckets
# ---------------------------------------------------------------------------

class BucketCreate(BaseModel):
    title: str
    job_description: str = ""
    requirements: list[dict] | None = None

class BucketUpdate(BaseModel):
    title: str | None = None
    job_description: str | None = None


@app.get("/api/buckets")
def api_list_buckets() -> list[dict[str, Any]]:
    return list_buckets()

@app.post("/api/buckets")
def api_create_bucket(body: BucketCreate) -> dict[str, Any]:
    if not body.title.strip():
        raise HTTPException(400, "Title is required")
    return create_bucket(body.title.strip(), body.job_description.strip(), body.requirements)

@app.get("/api/buckets/{bucket_id}")
def api_get_bucket(bucket_id: str) -> dict[str, Any]:
    try:
        return get_bucket(bucket_id)
    except Exception:
        raise HTTPException(404, "Bucket not found")

@app.patch("/api/buckets/{bucket_id}")
def api_update_bucket(bucket_id: str, body: BucketUpdate) -> dict[str, Any]:
    try:
        return update_bucket(bucket_id, title=body.title, job_description=body.job_description)
    except Exception:
        raise HTTPException(404, "Bucket not found")

@app.delete("/api/buckets/{bucket_id}")
def api_delete_bucket(bucket_id: str):
    delete_bucket(bucket_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bucket Requirements
# ---------------------------------------------------------------------------

class ReqCreate(BaseModel):
    label: str
    prompt: str
    weight: int = 1

class ReqUpdate(BaseModel):
    label: str | None = None
    prompt: str | None = None
    weight: int | None = None


class CandidateCreate(BaseModel):
    name: str = ""
    headline: str = ""
    location: str = ""
    summary: str = ""
    skills: list[str] = []
    links: list[dict[str, Any]] | None = None


class CandidateUpdate(BaseModel):
    name: str | None = None
    headline: str | None = None
    location: str | None = None
    summary: str | None = None
    skills: list[str] | None = None


@app.get("/api/buckets/{bucket_id}/requirements")
def api_list_requirements(bucket_id: str) -> list[dict[str, Any]]:
    return list_bucket_requirements(bucket_id)

@app.post("/api/buckets/{bucket_id}/requirements")
def api_create_requirement(bucket_id: str, body: ReqCreate) -> dict[str, Any]:
    if not body.label.strip() or not body.prompt.strip():
        raise HTTPException(400, "label and prompt are required")
    return create_bucket_requirement(bucket_id, body.label.strip(), body.prompt.strip(), body.weight)

@app.patch("/api/buckets/{bucket_id}/requirements/{req_id}")
def api_update_requirement(bucket_id: str, req_id: str, body: ReqUpdate) -> dict[str, Any]:
    try:
        return update_bucket_requirement(req_id, label=body.label, prompt=body.prompt, weight=body.weight)
    except Exception as e:
        raise HTTPException(400, str(e))

@app.delete("/api/buckets/{bucket_id}/requirements/{req_id}")
def api_delete_requirement(bucket_id: str, req_id: str):
    delete_bucket_requirement(req_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Bucket Candidates
# ---------------------------------------------------------------------------

@app.get("/api/buckets/{bucket_id}/candidates")
def api_list_candidates(bucket_id: str) -> list[dict[str, Any]]:
    return list_bucket_candidates(bucket_id)


@app.post("/api/buckets/{bucket_id}/candidates")
def api_create_candidate(bucket_id: str, body: CandidateCreate) -> dict[str, Any]:
    try:
        get_bucket(bucket_id)
    except Exception:
        raise HTTPException(404, "Bucket not found")
    try:
        return insert_bucket_candidate(
            bucket_id,
            name=body.name.strip() or "Unnamed",
            headline=body.headline.strip(),
            location=body.location.strip() or "Unknown",
            summary=body.summary.strip(),
            skills=body.skills or [],
            links=body.links,
        )
    except Exception as e:
        raise HTTPException(400, str(e))


@app.get("/api/buckets/{bucket_id}/candidates/{candidate_id}")
def api_get_candidate(bucket_id: str, candidate_id: str) -> dict[str, Any]:
    try:
        c = get_bucket_candidate(candidate_id)
        if c.get("bucket_id") != bucket_id:
            raise HTTPException(404, "Candidate not found")
        return c
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "Candidate not found")


@app.patch("/api/buckets/{bucket_id}/candidates/{candidate_id}")
def api_update_candidate(bucket_id: str, candidate_id: str, body: CandidateUpdate) -> dict[str, Any]:
    try:
        c = get_bucket_candidate(candidate_id)
        if c.get("bucket_id") != bucket_id:
            raise HTTPException(404, "Candidate not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "Candidate not found")
    try:
        update_bucket_candidate(
            candidate_id,
            name=body.name,
            headline=body.headline,
            location=body.location,
            summary=body.summary,
            skills=body.skills,
        )
        return get_bucket_candidate(candidate_id)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.delete("/api/buckets/{bucket_id}/candidates/{candidate_id}")
def api_delete_candidate(bucket_id: str, candidate_id: str):
    try:
        c = get_bucket_candidate(candidate_id)
        if c.get("bucket_id") != bucket_id:
            raise HTTPException(404, "Candidate not found")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(404, "Candidate not found")
    delete_bucket_candidate(candidate_id)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------

@app.post("/api/buckets/{bucket_id}/discover")
def api_discover(bucket_id: str) -> list[dict[str, Any]]:
    """Run web discovery for a bucket and save candidates to DB."""
    log.info("discover  started for bucket=%s", bucket_id)
    try:
        bucket = get_bucket(bucket_id)
    except Exception:
        raise HTTPException(404, "Bucket not found")

    if not bucket.get("job_description", "").strip():
        raise HTTPException(400, "Bucket has no job description")
    if not os.environ.get("SERPER_API_KEY"):
        raise HTTPException(400, "SERPER_API_KEY not configured")

    log.info("discover  running discovery agent for '%s'", bucket["title"])
    try:
        discovered = run_discovery(bucket["job_description"])
    except Exception as e:
        if _is_quota_error(e):
            raise HTTPException(429, "API quota / rate limit reached. Wait a minute and retry.")
        raise HTTPException(500, f"Discovery failed: {e}")

    log.info("discover  agent returned %d candidates, saving to DB", len(discovered))
    saved: list[dict[str, Any]] = []
    for i, c in enumerate(discovered, 1):
        try:
            row = insert_bucket_candidate(
                bucket_id=bucket_id,
                name=c.get("name", "Unknown"),
                headline=c.get("headline", ""),
                location=c.get("location", "Unknown"),
                summary=c.get("summary", ""),
                skills=c.get("skills", []),
                links=c.get("links", []),
            )
            saved.append(row)
            log.info("discover  saved candidate %d/%d: %s (%d links)", i, len(discovered), c.get("name", "?"), len(c.get("links", [])))
        except Exception as e:
            log.error("discover  failed to save candidate %d/%d: %s", i, len(discovered), e)

    log.info("discover  done, %d candidates saved for bucket=%s", len(saved), bucket_id)
    return saved


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

@app.post("/api/buckets/{bucket_id}/candidates/{candidate_id}/evaluate")
def api_evaluate_candidate(bucket_id: str, candidate_id: str) -> dict[str, Any]:
    """ReAct agent: fetch links intelligently, evaluate against requirements."""
    log.info("evaluate  started for candidate=%s bucket=%s", candidate_id, bucket_id)

    try:
        bucket = get_bucket(bucket_id)
    except Exception:
        raise HTTPException(404, "Bucket not found")

    try:
        candidate = get_bucket_candidate(candidate_id)
    except Exception:
        raise HTTPException(404, "Candidate not found")

    requirements = bucket.get("requirements", [])
    if not requirements:
        raise HTTPException(400, "Bucket has no requirements to evaluate against")

    links = candidate.get("links") or list_candidate_links(candidate_id)
    log.info("evaluate  candidate='%s', %d links, %d requirements",
             candidate.get("name", "?"), len(links), len(requirements))

    candidate_info = (
        f"Name: {candidate.get('name', '')}\n"
        f"Headline: {candidate.get('headline', '')}\n"
        f"Location: {candidate.get('location', '')}\n"
        f"Skills: {candidate.get('skills', [])}\n"
        f"Summary: {candidate.get('summary', '')}\n"
    )

    log.info("evaluate  running ReAct agent (max 4 tool loops + eval)...")
    try:
        agent_result = run_eval_agent(
            candidate_info=candidate_info,
            candidate_name=candidate.get("name", ""),
            candidate_id=candidate_id,
            initial_links=links,
            requirements=requirements,
        )
    except Exception as e:
        if _is_quota_error(e):
            raise HTTPException(429, "API quota / rate limit reached. Wait a minute and retry.")
        raise HTTPException(500, f"Evaluation failed: {e}")

    verdicts = agent_result.get("verdicts", {})
    evaluation_details = agent_result.get("evaluation_details")
    links_fetched = agent_result.get("links_fetched", [])

    log.info("evaluate  agent done — %d links fetched, persisting...", len(links_fetched))
    for lf in links_fetched:
        url = lf.get("url", "")
        if not url:
            continue
        try:
            link_row = ensure_candidate_link(
                candidate_id=candidate_id,
                url=url,
                label=url,
                link_type=lf.get("link_type", "web"),
                source="eval_agent",
            )
            upsert_link_fetch(
                candidate_link_id=link_row["id"],
                link_type=lf.get("link_type", "web"),
                content_type=lf.get("content_type", "text"),
                content_text=(lf.get("content_text") or "")[:50000],
                metadata=lf.get("metadata", {}),
            )
        except Exception as e:
            log.error("evaluate  failed to persist link %s: %s", url[:60], e)

    eval_rows = []
    for req in requirements:
        rid = req["id"]
        v = verdicts.get(rid, {"passed": False, "reason": "Not evaluated"})
        eval_rows.append({"requirement_id": rid, "passed": v["passed"], "reason": v.get("reason", "")})

    log.info("evaluate  saving evaluations to DB...")
    insert_candidate_evaluations(candidate_id, eval_rows)

    total_weight = sum(r.get("weight", 1) for r in requirements) or 1
    earned = sum(r.get("weight", 1) for r in requirements if verdicts.get(r["id"], {}).get("passed"))
    relevance = round((earned / total_weight) * 100)
    update_candidate_evaluation_status(candidate_id, relevance, evaluation_details=evaluation_details)

    passed = sum(1 for e in eval_rows if e["passed"])
    log.info("evaluate  done — relevance=%d%% (%d/%d passed) for candidate=%s",
             relevance, passed, len(eval_rows), candidate_id)

    return {
        "candidate_id": candidate_id,
        "relevance_percentage": relevance,
        "evaluations": eval_rows,
        "evaluation_details": evaluation_details,
    }
