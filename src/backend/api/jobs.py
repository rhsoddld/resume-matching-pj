from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from backend.schemas.job import JobMatchRequest, JobMatchResponse
from backend.services.matching_service import matching_service

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/match", response_model=JobMatchResponse)
def match_jobs(request: JobMatchRequest):
    """Match candidates to a job description."""
    return matching_service.match_jobs(
        job_description=request.job_description,
        top_k=request.top_k,
        category=request.category,
        min_experience_years=request.min_experience_years,
        education=request.education,
        region=request.region,
        industry=request.industry,
    )

@router.post("/match/stream")
def stream_match_jobs(request: JobMatchRequest):
    """Stream candidate match results iteratively via Server-Sent Events (SSE)."""
    generator = matching_service.stream_match_jobs(
        job_description=request.job_description,
        top_k=request.top_k,
        category=request.category,
        min_experience_years=request.min_experience_years,
        education=request.education,
        region=request.region,
        industry=request.industry,
    )
    return StreamingResponse(generator, media_type="text/event-stream")
