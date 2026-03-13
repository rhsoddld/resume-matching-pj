from fastapi import APIRouter, HTTPException
from backend.repositories.mongo_repo import get_candidate_by_id

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.get("/{candidate_id}")
def get_candidate(candidate_id: str):
    """Retrieve a single candidate by ID from MongoDB."""
    doc = get_candidate_by_id(candidate_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return doc
