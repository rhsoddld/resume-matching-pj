from fastapi import APIRouter, HTTPException
from backend.schemas.job import JobMatchRequest
from backend.services.matching_service import matching_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/match")
def match_jobs(request: JobMatchRequest):
    """Match candidates to a job describing text. (Happy Path / Base Version)"""
    try:
        results = matching_service.match_jobs(
            job_description=request.job_description,
            top_k=request.top_k,
            category=request.category,
            min_experience_years=request.min_experience_years
        )
        return {"matches": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
