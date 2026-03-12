"""Supabase client and DB helpers. All keys from env."""
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


def ensure_tables(supabase: Client) -> None:
    """Optional: document expected schema. Actual tables created in Supabase dashboard or migrations."""
    # Expected: candidates(id, name, email, resume_text, created_at)
    #           evaluations(id, candidate_id, requirement_id, passed, reason, created_at)
    pass


BUCKET_RESUME = "resume"


def insert_candidate(name: str, email: str, resume_text: str, resume_url: str | None = None) -> dict[str, Any]:
    supabase = get_supabase()
    row = {"name": name, "email": email, "resume_text": resume_text}
    if resume_url is not None:
        row["resume_url"] = resume_url
    r = supabase.table("candidates").insert(row).execute()
    if not r.data or len(r.data) == 0:
        raise RuntimeError("Failed to insert candidate")
    return r.data[0]


def upload_resume(candidate_id: str, filename: str, content: bytes) -> str:
    """Upload resume file to bucket 'resume'. Returns public URL."""
    import re
    supabase = get_supabase()
    safe = re.sub(r"[^\w.\-]", "_", filename)[:80]
    path = f"{candidate_id}/{safe}"
    supabase.storage.from_(BUCKET_RESUME).upload(path, content, {"content-type": "application/octet-stream", "upsert": "true"})
    r = supabase.storage.from_(BUCKET_RESUME).get_public_url(path)
    return r


def update_candidate_resume_url(candidate_id: str, resume_url: str) -> None:
    supabase = get_supabase()
    supabase.table("candidates").update({"resume_url": resume_url}).eq("id", candidate_id).execute()


def insert_evaluations(candidate_id: str, results: dict[str, dict]) -> None:
    supabase = get_supabase()
    rows = [
        {"candidate_id": candidate_id, "requirement_id": rid, "passed": v["passed"], "reason": v.get("reason", "")}
        for rid, v in results.items()
    ]
    supabase.table("evaluations").insert(rows).execute()


def get_requirements() -> list[dict[str, Any]]:
    supabase = get_supabase()
    r = supabase.table("requirements").select("id, label, prompt, weight, sort_order").order("sort_order").execute()
    return list(r.data or [])


def get_requirement_ids() -> list[str]:
    return [x["id"] for x in get_requirements()]


def get_candidates_with_scores() -> list[dict[str, Any]]:
    supabase = get_supabase()
    reqs = {r["id"]: r["weight"] for r in get_requirements()}
    max_score = sum(reqs.values()) or 1
    candidates = supabase.table("candidates").select("id, name, email, resume_url, created_at").order("created_at", desc=True).execute()
    evals = supabase.table("evaluations").select("candidate_id, requirement_id, passed, reason").execute()
    by_candidate: dict[str, dict] = {}
    for c in (candidates.data or []):
        cid = c["id"]
        by_candidate[cid] = {**c, "score": 0, "evaluations": []}
    for e in (evals.data or []):
        cid = e["candidate_id"]
        if cid in by_candidate:
            w = reqs.get(e["requirement_id"], 1)
            if e["passed"]:
                by_candidate[cid]["score"] += w
            by_candidate[cid]["evaluations"].append(e)
    out = list(by_candidate.values())
    for row in out:
        row["relevance_percentage"] = round((row["score"] / max_score) * 100)
    out.sort(key=lambda x: (-x["score"], x["name"]))
    return out


def get_candidate_evaluations(candidate_id: str) -> list[dict[str, Any]]:
    supabase = get_supabase()
    r = supabase.table("evaluations").select("requirement_id, passed, reason").eq("candidate_id", candidate_id).execute()
    return list(r.data or [])


def create_requirement(id: str, label: str, prompt: str, weight: int = 1) -> dict[str, Any]:
    supabase = get_supabase()
    max_order = supabase.table("requirements").select("sort_order").order("sort_order", desc=True).limit(1).execute()
    sort_order = (max_order.data[0]["sort_order"] + 1) if (max_order.data and len(max_order.data) > 0) else 0
    row = supabase.table("requirements").insert({"id": id, "label": label, "prompt": prompt, "weight": weight, "sort_order": sort_order}).execute()
    if not row.data:
        raise RuntimeError("Failed to create requirement")
    return row.data[0]


def update_requirement(id: str, label: str | None = None, prompt: str | None = None, weight: int | None = None) -> dict[str, Any]:
    from datetime import datetime, timezone
    supabase = get_supabase()
    updates: dict[str, Any] = {"updated_at": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")}
    if label is not None:
        updates["label"] = label
    if prompt is not None:
        updates["prompt"] = prompt
    if weight is not None:
        updates["weight"] = weight
    r = supabase.table("requirements").update(updates).eq("id", id).execute()
    if not r.data:
        raise RuntimeError("Requirement not found")
    return r.data[0]


def delete_requirement(id: str) -> None:
    supabase = get_supabase()
    supabase.table("requirements").delete().eq("id", id).execute()


def get_candidates_list() -> list[dict[str, Any]]:
    """List all candidates for admin (id, name, email, resume_url, created_at)."""
    supabase = get_supabase()
    r = supabase.table("candidates").select("id, name, email, resume_url, created_at").order("created_at", desc=True).execute()
    return list(r.data or [])


def update_candidate(candidate_id: str, name: str | None = None, email: str | None = None) -> dict[str, Any]:
    supabase = get_supabase()
    updates: dict[str, Any] = {}
    if name is not None:
        updates["name"] = name
    if email is not None:
        updates["email"] = email
    if not updates:
        raise ValueError("Nothing to update")
    r = supabase.table("candidates").update(updates).eq("id", candidate_id).execute()
    if not r.data:
        raise RuntimeError("Candidate not found")
    return r.data[0]


def delete_candidate(candidate_id: str) -> None:
    """Delete candidate; evaluations are deleted by FK cascade."""
    supabase = get_supabase()
    supabase.table("candidates").delete().eq("id", candidate_id).execute()
