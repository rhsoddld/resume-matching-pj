from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import tempfile
import shutil
import os
from pathlib import Path

from backend.schemas.job import JobFilterOptions, JobMatchRequest, JobMatchResponse
from backend.schemas.feedback import InterviewEmailRequest, InterviewEmailResponse
from backend.services.matching_service import matching_service
from backend.services.resume_parsing import extract_text_from_pdf
from backend.services.email_draft_service import generate_interview_email
from backend.repositories.session_repo import create_jd_session, get_jd_session
from backend.repositories.mongo_repo import get_filter_options
from backend.core.jd_guardrails import optimize_jd_tokens, scan_for_prompt_injection
from ops.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/filters", response_model=JobFilterOptions)
def filter_options():
    data = get_filter_options()
    return JobFilterOptions(
        job_families=data.get("job_families", []),
        educations=data.get("educations", []),
        regions=data.get("regions", []),
        industries=data.get("industries", []),
    )


@router.post("/match", response_model=JobMatchResponse)
def match_jobs(request: JobMatchRequest):
    """Match candidates to a job description."""
    if scan_for_prompt_injection(request.job_description):
        raise HTTPException(status_code=400, detail="Security Guardrail Blocked: Prompt injection detected (e.g. 'ignore previous instructions'). Please provide a valid Job Description.")

    safe_jd = optimize_jd_tokens(request.job_description)

    result: JobMatchResponse = matching_service.match_jobs(
        job_description=safe_jd,
        top_k=request.top_k,
        category=request.category,
        min_experience_years=request.min_experience_years,
        education=request.education,
        region=request.region,
        industry=request.industry,
    )

    # Persist JD session for feedback & email draft linkage (AHI.2 / AHI.4)
    try:
        session_id = create_jd_session(
            job_description=safe_jd,
            query_profile=result.query_profile.model_dump() if result.query_profile else None,
        )
        result.session_id = session_id
    except Exception as exc:
        logger.warning("Failed to create JD session (non-fatal): %s", exc)

    return result


@router.post("/match/stream")
def stream_match_jobs(request: JobMatchRequest):
    """Stream candidate match results iteratively via Server-Sent Events (SSE)."""
    if scan_for_prompt_injection(request.job_description):
        raise HTTPException(status_code=400, detail="Security Guardrail Blocked: Prompt injection detected (e.g. 'ignore previous instructions'). Please provide a valid Job Description.")

    safe_jd = optimize_jd_tokens(request.job_description)

    generator = matching_service.stream_match_jobs(
        job_description=safe_jd,
        top_k=request.top_k,
        category=request.category,
        min_experience_years=request.min_experience_years,
        education=request.education,
        region=request.region,
        industry=request.industry,
    )
    return StreamingResponse(generator, media_type="text/event-stream")


@router.post("/extract-pdf")
def extract_pdf(file: UploadFile = File(...)):
    """Extract text from an uploaded PDF Job Description."""
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        shutil.copyfileobj(file.file, tmp)
        tmp_path = Path(tmp.name)

    try:
        extracted_text = extract_text_from_pdf(tmp_path)
        if not extracted_text:
            raise HTTPException(status_code=422, detail="Failed to extract text from PDF or PDF is empty")
        return {"text": extracted_text}
    finally:
        if tmp_path.exists():
            os.remove(tmp_path)


@router.post("/draft-interview-email", response_model=InterviewEmailResponse)
def draft_interview_email(request: InterviewEmailRequest):
    """
    Generate an LLM-based interview invitation email draft (AHI.4).

    Retrieves the JD from the stored session and generates a personalised
    outreach email referencing the candidate's matching skills and experience.
    """
    session = get_jd_session(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session '{request.session_id}' not found. Run a match first.")

    job_description: str = session.get("job_description", "")
    if not job_description:
        raise HTTPException(status_code=422, detail="JD content is missing from session.")

    try:
        result = generate_interview_email(
            job_description=job_description,
            candidate=request.candidate,
        )
    except Exception as exc:
        logger.exception("Email draft generation failed.", exc_info=exc)
        raise HTTPException(status_code=500, detail=f"Email draft generation failed: {exc}") from exc

    return InterviewEmailResponse(subject=result["subject"], body=result["body"])
