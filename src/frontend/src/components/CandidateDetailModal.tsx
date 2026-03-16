import { useEffect, useMemo, useState, useCallback } from "react";
import type { FeedbackRating, InterviewEmailDraft, JobMatchCandidate, QueryUnderstandingProfile } from "../types";
import BiasGuardrailBanner from "./BiasGuardrailBanner";
import ExplainabilityPanel from "./ExplainabilityPanel";
import { isFastProfileCandidate } from "../utils/agentEvaluation";
import { submitFeedback, draftInterviewEmail } from "../api/feedback";

interface CandidateDetailModalProps {
  candidate: JobMatchCandidate | null;
  queryProfile: QueryUnderstandingProfile | null;
  jobDescription: string;
  sessionId?: string;
  onClose: () => void;
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function confidenceOrNull(value: unknown): number | null {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  const normalized = value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function formatExperienceYears(years: number | undefined): string {
  if (typeof years !== "number" || Number.isNaN(years)) {
    return "Experience not provided";
  }
  const rounded = Number.isInteger(years) ? years.toFixed(0) : years.toFixed(1);
  return `${rounded} years`;
}

function toNumber(value: unknown): number | null {
  if (typeof value === "number" && !Number.isNaN(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim() !== "" && !Number.isNaN(Number(value))) {
    return Number(value);
  }
  return null;
}

function formatWeightLine(label: string, value: unknown): string | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  const row = value as Record<string, unknown>;
  const skill = toNumber(row.skill);
  const experience = toNumber(row.experience);
  const technical = toNumber(row.technical);
  const culture = toNumber(row.culture);
  if ([skill, experience, technical, culture].some((v) => v == null)) {
    return null;
  }
  return `${label} (S:${(skill as number).toFixed(2)}, E:${(experience as number).toFixed(2)}, T:${(technical as number).toFixed(2)}, C:${(culture as number).toFixed(2)})`;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function normalizeToken(value: string): string {
  return value.trim().toLowerCase();
}

function includesTerm(text: string, term: string): boolean {
  const normalizedText = normalizeToken(text);
  const normalizedTerm = normalizeToken(term);
  return normalizedText.includes(normalizedTerm) || normalizedTerm.includes(normalizedText);
}

function fallbackFinalComment(candidate: JobMatchCandidate, matchedCount: number, requiredCount: number): string {
  const score = typeof candidate.score === "number" ? Math.round((candidate.score <= 1 ? candidate.score * 100 : candidate.score)) : 0;
  const gapCount = candidate.possible_gaps?.length ?? 0;
  if (score >= 80 && gapCount === 0) {
    return `Strong coverage on core requirements with low risk. Recommended for priority interview. (Requirement match ${matchedCount}/${requiredCount || matchedCount || 1})`;
  }
  if (gapCount > 0) {
    return `The baseline fit is solid, but there are ${gapCount} gaps that need validation. Please verify these in interview.`;
  }
  return `Overall score is ${score}. This candidate is viable with follow-up validation against core JD requirements.`;
}

const AGENT_SECTIONS: Array<{ key: string; label: string }> = [
  { key: "parsing", label: "Parsing" },
  { key: "skill", label: "Skill" },
  { key: "experience", label: "Experience" },
  { key: "technical", label: "Technical" },
  { key: "culture", label: "Culture" },
];

export default function CandidateDetailModal({ candidate, queryProfile, jobDescription, sessionId, onClose }: CandidateDetailModalProps) {
  const negotiationPack = toRecord(candidate?.agent_scores?.["weight_negotiation"]);
  const negotiationRationale = typeof negotiationPack?.rationale === "string"
    ? negotiationPack.rationale.trim()
    : "";
  const rankingExplanation = (candidate?.agent_explanation ?? "").trim();
  const runtimeMode = String(candidate?.agent_scores?.["runtime_mode"] ?? "");
  const runtimeReason = String(candidate?.agent_scores?.["runtime_reason"] ?? "").trim();
  const runtimeLabel = runtimeMode === "sdk_handoff"
    ? "A2A(Handoff)"
    : runtimeMode === "live_json"
      ? "Live JSON"
      : runtimeMode === "heuristic"
        ? "Fallback: Heuristic"
        : runtimeMode === "deterministic_only"
          ? "Deterministic only"
        : "";
  const recruiterLine = formatWeightLine("Recruiter proposal", negotiationPack?.recruiter);
  const hiringLine = formatWeightLine("Hiring manager proposal", negotiationPack?.hiring_manager);
  const finalLine = formatWeightLine("Final policy", negotiationPack?.final);

  const warnings = useMemo(() => {
    if (!candidate) {
      return [];
    }

    const isFastProfile = isFastProfileCandidate(candidate);
    const list: string[] = [...(candidate.bias_warnings ?? [])];
    if ((candidate.possible_gaps?.length ?? 0) > 2) {
      list.push("Several potential skill gaps were detected. Validate job-critical requirements manually.");
    }
    const cultureConfidence = isFastProfile
      ? null
      : confidenceOrNull(toRecord(candidate.agent_scores.confidence)?.culture ?? candidate.agent_scores.culture);
    if (!isFastProfile && cultureConfidence !== null && cultureConfidence < 40) {
      list.push("Culture-fit confidence is low. Use structured interviews before making decisions.");
    }
    return Array.from(new Set(list));
  }, [candidate]);

  // AHI.2 – Recruiter feedback state
  const [activeFeedback, setActiveFeedback] = useState<FeedbackRating | null>(null);
  const [feedbackLoading, setFeedbackLoading] = useState(false);

  // AHI.4 – Interview email draft state
  const [emailDraft, setEmailDraft] = useState<InterviewEmailDraft | null>(null);
  const [emailLoading, setEmailLoading] = useState(false);
  const [emailError, setEmailError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleFeedback = useCallback(async (rating: FeedbackRating) => {
    if (!candidate || !sessionId) return;
    setFeedbackLoading(true);
    try {
      await submitFeedback(sessionId, candidate.candidate_id, rating);
      setActiveFeedback(rating);
    } catch {
      // silently ignore; button still toggles optimistically
      setActiveFeedback(rating);
    } finally {
      setFeedbackLoading(false);
    }
  }, [candidate, sessionId]);

  const handleDraftEmail = useCallback(async () => {
    if (!candidate || !sessionId) return;
    setEmailLoading(true);
    setEmailError(null);
    setEmailDraft(null);
    setCopied(false);
    try {
      const draft = await draftInterviewEmail(sessionId, candidate.candidate_id, candidate);
      setEmailDraft(draft);
    } catch (err) {
      setEmailError(err instanceof Error ? err.message : "Failed to generate email draft.");
    } finally {
      setEmailLoading(false);
    }
  }, [candidate, sessionId]);

  const handleCopy = useCallback(() => {
    if (!emailDraft) return;
    const text = `Subject: ${emailDraft.subject}\n\n${emailDraft.body}`;
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [emailDraft]);

  // Reset email draft and feedback when candidate changes
  useEffect(() => {
    setEmailDraft(null);
    setEmailError(null);
    setActiveFeedback(null);
    setCopied(false);
  }, [candidate?.candidate_id]);

  const requirementInfo = useMemo(() => {
    if (!queryProfile) {
      return {
        requiredSkills: [] as string[],
        relatedSkills: [] as string[],
        minExperienceYears: null as number | null,
      };
    }

    const fromFilters = toNumber(queryProfile.filters?.min_experience_years);
    const fromMetadata = toNumber(queryProfile.metadata_filters?.min_experience_years);
    return {
      requiredSkills: queryProfile.required_skills ?? [],
      relatedSkills: queryProfile.related_skills ?? [],
      minExperienceYears: fromFilters ?? fromMetadata,
    };
  }, [queryProfile]);

  const jdMatch = useMemo(() => {
    if (!candidate) {
      return { matchedRequired: [] as string[], matchedRelated: [] as string[], highlightTerms: [] as string[] };
    }

    const candidateSkillPool = [
      ...(candidate.normalized_skills ?? []),
      ...(candidate.skills ?? []),
      ...(candidate.core_skills ?? []),
      ...(candidate.expanded_skills ?? []),
      ...(candidate.adjacent_skill_matches ?? []),
    ];

    const matchedRequired = requirementInfo.requiredSkills.filter((term) =>
      candidateSkillPool.some((skill) => includesTerm(skill, term))
    );
    const matchedRelated = requirementInfo.relatedSkills.filter((term) =>
      candidateSkillPool.some((skill) => includesTerm(skill, term))
    );

    const highlightTerms = Array.from(new Set([...matchedRequired, ...matchedRelated]))
      .map((term) => term.trim())
      .filter((term) => term.length >= 2)
      .sort((a, b) => b.length - a.length)
      .slice(0, 24);

    return { matchedRequired, matchedRelated, highlightTerms };
  }, [candidate, requirementInfo.relatedSkills, requirementInfo.requiredSkills]);

  const finalComment = useMemo(() => {
    if (!candidate) {
      return "";
    }
    if (candidate.agent_explanation && candidate.agent_explanation.trim() !== "") {
      return candidate.agent_explanation;
    }
    if (candidate.weighting_summary && candidate.weighting_summary.trim() !== "") {
      return candidate.weighting_summary;
    }
    return fallbackFinalComment(candidate, jdMatch.matchedRequired.length, requirementInfo.requiredSkills.length);
  }, [candidate, jdMatch.matchedRequired.length, requirementInfo.requiredSkills.length]);

  useEffect(() => {
    if (!candidate) {
      return undefined;
    }

    function onKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", onKeydown);
    return () => {
      window.removeEventListener("keydown", onKeydown);
    };
  }, [candidate, onClose]);

  if (!candidate) {
    return null;
  }
  const isFastProfile = isFastProfileCandidate(candidate);

  const safeJobDescription = jobDescription.trim();
  const highlightRegex = jdMatch.highlightTerms.length > 0
    ? new RegExp(`(${jdMatch.highlightTerms.map((term) => escapeRegExp(term)).join("|")})`, "gi")
    : null;
  const jdParts = highlightRegex ? safeJobDescription.split(highlightRegex) : [safeJobDescription];

  return (
    <div
      className="candidate-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Candidate detail modal"
      onClick={onClose}
    >
      <div className="candidate-modal" onClick={(event) => event.stopPropagation()}>
        <header className="candidate-modal__header">
          <div>
            <h2>
              {candidate.candidate_id}
            </h2>
            <p>
              {candidate.seniority_level || candidate.category || "Candidate profile"}
              {" · "}
              {formatExperienceYears(candidate.experience_years)}
            </p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close details">
            Close
          </button>
        </header>

        <BiasGuardrailBanner warnings={warnings} />

        <div className="candidate-modal__body">
          <section className="candidate-modal__left">
            <article className="detail-panel">
              <h3>Summary</h3>
              <p>{candidate.summary ?? "No summary provided."}</p>
            </article>

            <article className="detail-panel">
              <h3>Key Experience</h3>
              <ul>
                {(candidate.relevant_experience ?? []).slice(0, 6).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>

            <article className="detail-panel">
              <h3>Projects / Signals</h3>
              <div className="chip-list">
                {candidate.core_skills.slice(0, 10).map((skill) => (
                  <span className="chip" key={skill}>{skill}</span>
                ))}
              </div>
            </article>

            <article className="detail-panel">
              <h3>JD Requirements</h3>
              <div className="jd-requirements-grid">
                <div>
                  <strong>Core requirements</strong>
                  <div className="chip-list">
                    {requirementInfo.requiredSkills.length > 0 ? requirementInfo.requiredSkills.map((skill) => (
                      <span
                        key={`required-${skill}`}
                        className={`chip ${jdMatch.matchedRequired.includes(skill) ? "chip--matched" : "chip--missing"}`}
                      >
                        {skill}
                      </span>
                    )) : <span className="chip chip--neutral">No extracted core requirements</span>}
                  </div>
                </div>
                <div>
                  <strong>Related requirements</strong>
                  <div className="chip-list">
                    {requirementInfo.relatedSkills.length > 0 ? requirementInfo.relatedSkills.slice(0, 16).map((skill) => (
                      <span
                        key={`related-${skill}`}
                        className={`chip ${jdMatch.matchedRelated.includes(skill) ? "chip--matched" : "chip--neutral"}`}
                      >
                        {skill}
                      </span>
                    )) : <span className="chip chip--neutral">No related requirements</span>}
                  </div>
                </div>
              </div>
              {typeof requirementInfo.minExperienceYears === "number" && (
                <p className="jd-exp-line">Required experience: {requirementInfo.minExperienceYears}+ years</p>
              )}
            </article>

            <article className="detail-panel">
              <h3>JD Match Highlights</h3>
              {safeJobDescription ? (
                <p className="jd-highlight-text">
                  {jdParts.map((part, idx) => {
                    const isMatched = jdMatch.highlightTerms.some((term) => term.toLowerCase() === part.toLowerCase());
                    if (!isMatched) {
                      return <span key={`text-${idx}`}>{part}</span>;
                    }
                    return <mark key={`mark-${idx}`} className="jd-match-mark">{part}</mark>;
                  })}
                </p>
              ) : (
                <p>Job description input is not available.</p>
              )}
            </article>

            <article className="detail-panel detail-panel--comment">
              <h3>Final Agent Comment</h3>
              {runtimeLabel && <p className="runtime-status-line">{runtimeLabel}</p>}
              {runtimeReason && <p className="runtime-reason-line">Reason: {runtimeReason}</p>}
              {(recruiterLine || hiringLine || finalLine) && (
                <ul className="detail-list">
                  {recruiterLine && <li>{recruiterLine}</li>}
                  {hiringLine && <li>{hiringLine}</li>}
                  {finalLine && <li>{finalLine}</li>}
                </ul>
              )}
              {negotiationRationale && (
                <>
                  <strong>Negotiation rationale</strong>
                  <p>{negotiationRationale}</p>
                </>
              )}
              {rankingExplanation ? (
                <>
                  <strong>Ranking explanation</strong>
                  <p>{rankingExplanation}</p>
                </>
              ) : (
                <p>{finalComment}</p>
              )}
            </article>
          </section>

          <aside className="candidate-modal__right">
            <ExplainabilityPanel candidate={candidate} />

            <section className="agent-eval-panel" aria-label="AI evaluation panel">
              <h3>Multi-agent Evaluation</h3>
              <div className="agent-list">
                {AGENT_SECTIONS.map((section) => {
                  const confidencePack = toRecord(candidate.agent_scores.confidence);
                  const confidence = confidenceOrNull(confidencePack?.[section.key] ?? candidate.agent_scores[section.key]);
                  const evidencePack = toRecord(candidate.agent_scores.evidence);
                  const evidenceList = evidencePack?.[section.key];
                  const notEvaluated = section.key !== "parsing" && (isFastProfile || confidence === null);
                  const evidenceText = notEvaluated
                    ? (runtimeReason || "Not evaluated in this run (outside AGENT_EVAL_TOP_N scope).")
                    : (Array.isArray(evidenceList) && evidenceList.length > 0
                      ? String(evidenceList[0])
                      : ((confidence ?? 0) >= 60 ? "Strong signal from profile content" : "Limited explicit evidence"));
                  return (
                    <article key={section.key} className="agent-card">
                      <div>
                        <strong>{section.label}</strong>
                        <p>Confidence {notEvaluated ? "N/A" : `${confidence ?? 0}%`}</p>
                      </div>
                      <p className="agent-evidence">Evidence: {evidenceText}</p>
                    </article>
                  );
                })}
              </div>
            </section>
          </aside>
        </div>

        {/* AHI.2 + AHI.4 – Recruiter Action Bar */}
        <footer className="candidate-modal__action-bar">
          <div className="action-bar__feedback">
            <span className="action-bar__label">Recruiter Decision</span>

            {activeFeedback ? (
              /* ── 선택 완료 상태: badge만 표시 ── */
              <div className="feedback-decided">
                <span className={`feedback-decided__badge feedback-decided__badge--${activeFeedback}`}>
                  {activeFeedback === "pass" && <>✔︎ Passed</>}
                  {activeFeedback === "reject" && <>✕ Rejected</>}
                  {activeFeedback === "review" && <>● Needs Review</>}
                </span>
                <span className="feedback-decided__hint">Saved to session</span>
              </div>
            ) : (
              /* ── 미선택 상태: 버튼 3개 ── */
              <div className="action-bar__buttons">
                {(["pass", "reject", "review"] as FeedbackRating[]).map((rating) => {
                  const meta: Record<FeedbackRating, { label: string; mark: string }> = {
                    pass:   { label: "Pass",         mark: "✔︎" },
                    reject: { label: "Reject",       mark: "✕" },
                    review: { label: "Needs Review", mark: "●" },
                  };
                  return (
                    <button
                      key={rating}
                      type="button"
                      id={`feedback-btn-${rating}`}
                      disabled={feedbackLoading || !sessionId}
                      onClick={() => handleFeedback(rating)}
                      className={`feedback-btn feedback-btn--${rating}`}
                      title={!sessionId ? "Run a match first to enable feedback" : undefined}
                    >
                      <span className="feedback-btn__mark">{meta[rating].mark}</span>
                      {meta[rating].label}
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="action-bar__email">
            <button
              type="button"
              id="draft-email-btn"
              disabled={emailLoading || !sessionId}
              onClick={handleDraftEmail}
              className="email-draft-btn"
              title={!sessionId ? "Run a match first to enable email draft" : undefined}
            >
              {emailLoading ? (
                <><span className="spinner" /> Generating…</>
              ) : (
                <>&#9993; Draft Interview Email</>
              )}
            </button>

            {emailError && (
              <p className="email-draft-error">{emailError}</p>
            )}

            {emailDraft && (
              <div className="email-draft-panel">
                <div className="email-draft-panel__header">
                  <strong>Email Draft</strong>
                  <button
                    type="button"
                    id="copy-email-btn"
                    className="copy-btn"
                    onClick={handleCopy}
                  >
                    {copied ? "Copied!" : "Copy"}
                  </button>
                </div>
                <p className="email-draft-subject"><strong>Subject:</strong> {emailDraft.subject}</p>
                <pre className="email-draft-body">{emailDraft.body}</pre>
              </div>
            )}
          </div>
        </footer>
      </div>
    </div>
  );
}
