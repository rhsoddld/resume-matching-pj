"""LLM-based interview invitation email draft service (AHI.4)."""
from __future__ import annotations

import os
from typing import Optional

from openai import OpenAI

from backend.schemas.job import JobMatchCandidate


_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def _build_prompt(
    job_description: str,
    candidate: JobMatchCandidate,
) -> str:
    skills_str = ", ".join(candidate.core_skills[:10] or candidate.skills[:10])
    exp_str = f"{candidate.experience_years:.1f}" if candidate.experience_years else "N/A"
    seniority_str = candidate.seniority_level or candidate.category or "candidate"
    gaps_str = (
        ", ".join(candidate.possible_gaps[:4])
        if candidate.possible_gaps
        else "None identified"
    )
    matched_skills_str = (
        ", ".join(candidate.adjacent_skill_matches[:6])
        if candidate.adjacent_skill_matches
        else skills_str
    )

    jd_snippet = job_description[:800].strip()

    return f"""You are a professional recruiter drafting an initial outreach email to a candidate.

== Job Description (excerpt) ==
{jd_snippet}

== Candidate Summary ==
- ID/Name: {candidate.candidate_id}
- Seniority: {seniority_str}
- Experience: {exp_str} years
- Key Skills: {skills_str}
- Skills matching this role: {matched_skills_str}
- Potential gaps to discuss: {gaps_str}
- Overall match score: {round(candidate.score * 100 if candidate.score <= 1 else candidate.score)}%

== Instructions ==
Write a professional, warm, and concise email that:
1. Introduces the recruiter (use placeholder "[Recruiter Name]" and company "[Company Name]")
2. Briefly describes the role (draw from the JD excerpt, 1-2 sentences)
3. Specifically mentions 2-3 skills/experiences of the candidate that make them a great fit
4. Asks if the candidate is interested in having a short exploratory interview
5. Ends with a clear call-to-action (reply or schedule a call)

Format your response EXACTLY as:
SUBJECT: <email subject line>
BODY:
<email body>

Keep the body under 180 words. Write in a professional but friendly tone.
Match the language to the job description language (Korean JD → Korean email, English JD → English email).
"""


def generate_interview_email(
    job_description: str,
    candidate: JobMatchCandidate,
) -> dict[str, str]:
    """
    Call LLM to generate a personalized interview interest email draft.

    Returns a dict with 'subject' and 'body' keys.
    """
    prompt = _build_prompt(job_description, candidate)

    client = _get_client()
    response = client.chat.completions.create(
        model=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=600,
    )

    raw = response.choices[0].message.content or ""

    # Parse SUBJECT / BODY from LLM output
    subject = ""
    body = ""

    lines = raw.strip().splitlines()
    body_lines: list[str] = []
    in_body = False

    for line in lines:
        if line.upper().startswith("SUBJECT:"):
            subject = line[len("SUBJECT:"):].strip()
        elif line.upper().startswith("BODY:"):
            in_body = True
        elif in_body:
            body_lines.append(line)

    body = "\n".join(body_lines).strip()

    # Fallback: if parsing fails, use the full raw text as body
    if not subject:
        subject = f"Interview Opportunity – {candidate.candidate_id}"
    if not body:
        body = raw.strip()

    return {"subject": subject, "body": body}
