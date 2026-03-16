"""Recruiter feedback annotation API (AHI.2)."""
from fastapi import APIRouter, HTTPException

from backend.repositories.session_repo import save_feedback, get_session_feedbacks
from backend.schemas.feedback import CandidateFeedbackRequest

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post(
    "/sessions/{session_id}/candidates/{candidate_id}",
    summary="Submit recruiter feedback for a candidate in a session",
)
def submit_feedback(
    session_id: str,
    candidate_id: str,
    body: CandidateFeedbackRequest,
):
    """
    Upsert a recruiter annotation (pass / reject / review) for a specific
    candidate within a JD session. Linked by session_id + candidate_id.
    """
    try:
        save_feedback(
            session_id=session_id,
            candidate_id=candidate_id,
            rating=body.rating,
            notes=body.notes,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to save feedback: {exc}") from exc

    return {"ok": True, "session_id": session_id, "candidate_id": candidate_id, "rating": body.rating}


@router.get(
    "/sessions/{session_id}",
    summary="Get all recruiter feedback for a session",
)
def get_session_feedback(session_id: str):
    """
    Return all candidate feedback records associated with a JD session.
    Useful for the recruiter to review all pass/reject/review decisions in one place.
    """
    try:
        records = get_session_feedbacks(session_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve feedbacks: {exc}") from exc

    return {"session_id": session_id, "feedbacks": records}
