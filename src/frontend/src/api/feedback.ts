import type { FeedbackRating, InterviewEmailDraft, JobMatchCandidate } from "../types";

const BASE_URL = "/api";

export async function submitFeedback(
  sessionId: string,
  candidateId: string,
  rating: FeedbackRating,
  notes?: string
): Promise<void> {
  const response = await fetch(
    `${BASE_URL}/feedback/sessions/${encodeURIComponent(sessionId)}/candidates/${encodeURIComponent(candidateId)}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rating, notes: notes ?? null }),
    }
  );
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
}

export async function draftInterviewEmail(
  sessionId: string,
  candidateId: string,
  candidate: JobMatchCandidate
): Promise<InterviewEmailDraft> {
  const response = await fetch(`${BASE_URL}/jobs/draft-interview-email`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, candidate_id: candidateId, candidate }),
  });
  if (!response.ok) {
    let message = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") message = data.detail;
    } catch {
      // ignore
    }
    throw new Error(message);
  }
  return response.json() as Promise<InterviewEmailDraft>;
}
