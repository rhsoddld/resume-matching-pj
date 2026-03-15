from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import StreamingResponse
import tempfile
import shutil
import os
from pathlib import Path

from backend.schemas.job import JobMatchRequest, JobMatchResponse
from backend.services.matching_service import matching_service
from backend.services.resume_parsing import extract_text_from_pdf
from backend.core.jd_guardrails import optimize_jd_tokens, scan_for_prompt_injection

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/match", response_model=JobMatchResponse)
def match_jobs(request: JobMatchRequest):
    """Match candidates to a job description."""
    if scan_for_prompt_injection(request.job_description):
        raise HTTPException(status_code=400, detail="Security Guardrail Blocked: Prompt injection detected (e.g. 'ignore previous instructions'). Please provide a valid Job Description.")
        
    safe_jd = optimize_jd_tokens(request.job_description)
    
    return matching_service.match_jobs(
        job_description=safe_jd,
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
