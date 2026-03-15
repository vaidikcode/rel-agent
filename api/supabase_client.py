"""Supabase client and DB helpers for the Job Bucket model."""
import json
import os
from typing import Any

from supabase import create_client, Client

_url = os.environ.get("SUPABASE_URL")
_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
_client: Client | None = None


def get_supabase() -> Client:
    global _client
    if _client is not None:
        return _client
    if not _url or not _key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) must be set")
    _client = create_client(_url, _key)
    return _client


# ---------------------------------------------------------------------------
# Job Buckets
# ---------------------------------------------------------------------------

def list_buckets() -> list[dict[str, Any]]:
    sb = get_supabase()
    r = sb.table("job_buckets").select("*").order("created_at", desc=True).execute()
    buckets = list(r.data or [])
    if buckets:
        counts = sb.table("bucket_candidates").select("bucket_id").execute()
        counter: dict[str, int] = {}
        for row in (counts.data or []):
            bid = row["bucket_id"]
            counter[bid] = counter.get(bid, 0) + 1
        for b in buckets:
            b["candidate_count"] = counter.get(b["id"], 0)
    return buckets


def get_bucket(bucket_id: str) -> dict[str, Any]:
    sb = get_supabase()
    r = sb.table("job_buckets").select("*").eq("id", bucket_id).single().execute()
    bucket = r.data
    if not bucket:
        raise RuntimeError("Bucket not found")
    reqs = sb.table("bucket_requirements").select("*").eq("bucket_id", bucket_id).order("sort_order").execute()
    bucket["requirements"] = list(reqs.data or [])
    count = sb.table("bucket_candidates").select("id", count="exact").eq("bucket_id", bucket_id).execute()
    bucket["candidate_count"] = count.count if hasattr(count, "count") and count.count is not None else len(count.data or [])
    return bucket


def create_bucket(title: str, job_description: str, requirements: list[dict] | None = None) -> dict[str, Any]:
    sb = get_supabase()
    r = sb.table("job_buckets").insert({"title": title, "job_description": job_description}).execute()
    if not r.data:
        raise RuntimeError("Failed to create bucket")
    bucket = r.data[0]
    if requirements:
        rows = []
        for i, req in enumerate(requirements):
            rows.append({
                "bucket_id": bucket["id"],
                "label": req["label"],
                "prompt": req.get("prompt", ""),
                "weight": req.get("weight", 1),
                "sort_order": i,
            })
        sb.table("bucket_requirements").insert(rows).execute()
    return get_bucket(bucket["id"])


def update_bucket(bucket_id: str, title: str | None = None, job_description: str | None = None) -> dict[str, Any]:
    from datetime import datetime, timezone
    sb = get_supabase()
    updates: dict[str, Any] = {"updated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")}
    if title is not None:
        updates["title"] = title
    if job_description is not None:
        updates["job_description"] = job_description
    r = sb.table("job_buckets").update(updates).eq("id", bucket_id).execute()
    if not r.data:
        raise RuntimeError("Bucket not found")
    return r.data[0]


def delete_bucket(bucket_id: str) -> None:
    sb = get_supabase()
    sb.table("job_buckets").delete().eq("id", bucket_id).execute()


# ---------------------------------------------------------------------------
# Bucket Requirements
# ---------------------------------------------------------------------------

def list_bucket_requirements(bucket_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    r = sb.table("bucket_requirements").select("*").eq("bucket_id", bucket_id).order("sort_order").execute()
    return list(r.data or [])


def create_bucket_requirement(bucket_id: str, label: str, prompt: str, weight: int = 1) -> dict[str, Any]:
    sb = get_supabase()
    max_order = sb.table("bucket_requirements").select("sort_order").eq("bucket_id", bucket_id).order("sort_order", desc=True).limit(1).execute()
    sort_order = (max_order.data[0]["sort_order"] + 1) if max_order.data else 0
    r = sb.table("bucket_requirements").insert({
        "bucket_id": bucket_id, "label": label, "prompt": prompt, "weight": weight, "sort_order": sort_order,
    }).execute()
    if not r.data:
        raise RuntimeError("Failed to create requirement")
    return r.data[0]


def update_bucket_requirement(req_id: str, label: str | None = None, prompt: str | None = None, weight: int | None = None) -> dict[str, Any]:
    sb = get_supabase()
    updates: dict[str, Any] = {}
    if label is not None:
        updates["label"] = label
    if prompt is not None:
        updates["prompt"] = prompt
    if weight is not None:
        updates["weight"] = weight
    if not updates:
        raise ValueError("Nothing to update")
    r = sb.table("bucket_requirements").update(updates).eq("id", req_id).execute()
    if not r.data:
        raise RuntimeError("Requirement not found")
    return r.data[0]


def delete_bucket_requirement(req_id: str) -> None:
    sb = get_supabase()
    sb.table("bucket_requirements").delete().eq("id", req_id).execute()


# ---------------------------------------------------------------------------
# Bucket Candidates
# ---------------------------------------------------------------------------

def list_bucket_candidates(bucket_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    r = sb.table("bucket_candidates").select("*").eq("bucket_id", bucket_id).order("created_at", desc=True).execute()
    return list(r.data or [])


def get_bucket_candidate(candidate_id: str) -> dict[str, Any]:
    sb = get_supabase()
    r = sb.table("bucket_candidates").select("*").eq("id", candidate_id).single().execute()
    candidate = r.data
    if not candidate:
        raise RuntimeError("Candidate not found")
    links = sb.table("candidate_links").select("*").eq("candidate_id", candidate_id).execute()
    candidate["links"] = list(links.data or [])
    evals = sb.table("candidate_evaluations").select("*").eq("candidate_id", candidate_id).execute()
    evals_list = list(evals.data or [])
    # Enrich with requirement labels so UI shows labels instead of UUIDs
    reqs = list_bucket_requirements(candidate["bucket_id"])
    req_labels = {req["id"]: req.get("label", "") for req in reqs}
    for e in evals_list:
        e["requirement_label"] = req_labels.get(e["requirement_id"], e["requirement_id"])
    candidate["evaluations"] = evals_list
    return candidate


def insert_bucket_candidate(bucket_id: str, name: str, headline: str, location: str, summary: str, skills: list[str], links: list[dict] | None = None) -> dict[str, Any]:
    sb = get_supabase()
    r = sb.table("bucket_candidates").insert({
        "bucket_id": bucket_id,
        "name": name,
        "headline": headline,
        "location": location,
        "summary": summary,
        "skills": json.dumps(skills),
        "status": "discovered",
    }).execute()
    if not r.data:
        raise RuntimeError("Failed to insert candidate")
    candidate = r.data[0]
    if links:
        link_rows = [
            {"candidate_id": candidate["id"], "url": l["url"], "label": l.get("label", ""), "source": l.get("source", "discovery")}
            for l in links if l.get("url")
        ]
        if link_rows:
            sb.table("candidate_links").insert(link_rows).execute()
    return candidate


def delete_bucket_candidate(candidate_id: str) -> None:
    sb = get_supabase()
    sb.table("bucket_candidates").delete().eq("id", candidate_id).execute()


# ---------------------------------------------------------------------------
# Candidate Links
# ---------------------------------------------------------------------------

def list_candidate_links(candidate_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    r = sb.table("candidate_links").select("*").eq("candidate_id", candidate_id).execute()
    return list(r.data or [])


# ---------------------------------------------------------------------------
# Candidate Evaluations
# ---------------------------------------------------------------------------

def insert_candidate_evaluations(candidate_id: str, results: list[dict]) -> None:
    """Insert evaluation verdicts and update candidate status + relevance."""
    sb = get_supabase()
    rows = [
        {"candidate_id": candidate_id, "requirement_id": r["requirement_id"], "passed": r["passed"], "reason": r.get("reason", "")}
        for r in results
    ]
    if rows:
        sb.table("candidate_evaluations").insert(rows).execute()


def update_candidate_evaluation_status(candidate_id: str, relevance_percentage: int) -> None:
    sb = get_supabase()
    sb.table("bucket_candidates").update({
        "status": "evaluated",
        "relevance_percentage": relevance_percentage,
    }).eq("id", candidate_id).execute()


def get_candidate_evaluations(candidate_id: str) -> list[dict[str, Any]]:
    sb = get_supabase()
    r = sb.table("candidate_evaluations").select("*").eq("candidate_id", candidate_id).execute()
    return list(r.data or [])
