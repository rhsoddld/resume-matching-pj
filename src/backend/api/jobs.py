from fastapi import APIRouter

from backend.schemas.job import JobMatchRequest, JobMatchResponse
from backend.services.matching_service import matching_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/match", response_model=JobMatchResponse)
def match_jobs(request: JobMatchRequest):
    """Match candidates to a job description."""
    results = matching_service.match_jobs(
        job_description=request.job_description,
        top_k=request.top_k,
        category=request.category,
        min_experience_years=request.min_experience_years,
    )
    return JobMatchResponse(matches=results)
