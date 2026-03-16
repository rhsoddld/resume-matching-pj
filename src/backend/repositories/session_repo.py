"""Repository for JD sessions and candidate feedback (AHI.2 & AHI.4)."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from backend.core.database import get_collection
from backend.core.exceptions import RepositoryError


def _new_session_id() -> str:
    return str(uuid.uuid4())


# ──────────────────────────────────────────────
# JD Session CRUD
# ──────────────────────────────────────────────

def create_jd_session(job_description: str, query_profile: Optional[dict] = None) -> str:
    """Persist a JD session and return the generated session_id."""
    session_id = _new_session_id()
    doc = {
        "session_id": session_id,
        "job_description": job_description,
        "query_profile": query_profile,
        "created_at": datetime.utcnow(),
    }
    try:
        coll = get_collection("jd_sessions")
        coll.insert_one(doc)
    except Exception as exc:
        raise RepositoryError("Failed to create JD session.") from exc
    return session_id


def get_jd_session(session_id: str) -> Optional[dict]:
    """Retrieve a JD session document by session_id."""
    try:
        coll = get_collection("jd_sessions")
        doc = coll.find_one({"session_id": session_id}, {"_id": 0})
        return doc
    except Exception as exc:
        raise RepositoryError("Failed to retrieve JD session.") from exc


# ──────────────────────────────────────────────
# Candidate Feedback CRUD
# ──────────────────────────────────────────────

def save_feedback(
    session_id: str,
    candidate_id: str,
    rating: str,
    notes: Optional[str] = None,
) -> None:
    """Upsert a recruiter feedback annotation for a session+candidate pair."""
    doc = {
        "session_id": session_id,
        "candidate_id": candidate_id,
        "rating": rating,
        "notes": notes,
        "created_at": datetime.utcnow(),
    }
    try:
        coll = get_collection("candidate_feedback")
        coll.update_one(
            {"session_id": session_id, "candidate_id": candidate_id},
            {"$set": doc},
            upsert=True,
        )
    except Exception as exc:
        raise RepositoryError("Failed to save candidate feedback.") from exc


def get_session_feedbacks(session_id: str) -> list[dict]:
    """Return all feedback records for a given session."""
    try:
        coll = get_collection("candidate_feedback")
        docs = list(coll.find({"session_id": session_id}, {"_id": 0}))
        return docs
    except Exception as exc:
        raise RepositoryError("Failed to retrieve session feedbacks.") from exc
