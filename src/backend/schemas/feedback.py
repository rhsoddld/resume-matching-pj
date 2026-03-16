"""Schemas for recruiter feedback (AHI.2) and interview email draft (AHI.4)."""
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

from backend.schemas.job import JobMatchCandidate, QueryUnderstandingProfile


FeedbackRating = Literal["pass", "reject", "review"]


class JDSession(BaseModel):
    """Stored when a match request is executed. Links JD to subsequent feedback."""
    session_id: str
    job_description: str
    query_profile: Optional[QueryUnderstandingProfile] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CandidateFeedbackRequest(BaseModel):
    """Request body for submitting recruiter feedback on a candidate."""
    rating: FeedbackRating
    notes: Optional[str] = Field(default=None, max_length=1000)


class CandidateFeedbackRecord(BaseModel):
    """Stored annotation record linking session, candidate, and recruiter rating."""
    session_id: str
    candidate_id: str
    rating: FeedbackRating
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewEmailRequest(BaseModel):
    """Request body for generating an interview interest email draft."""
    session_id: str
    candidate_id: str
    candidate: JobMatchCandidate


class InterviewEmailResponse(BaseModel):
    """LLM-generated interview invitation email draft."""
    subject: str
    body: str
    generated_at: datetime = Field(default_factory=datetime.utcnow)
