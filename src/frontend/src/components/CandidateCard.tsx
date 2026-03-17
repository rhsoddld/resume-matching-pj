import MatchScorePill from "./MatchScorePill";
import type { JobMatchCandidate } from "../types";
import { isFastProfileCandidate } from "../utils/agentEvaluation";

interface CandidateCardProps {
  candidate: JobMatchCandidate;
  onOpen: (candidate: JobMatchCandidate) => void;
}

function scoreToPercent(raw: number | undefined): number {
  if (typeof raw !== "number" || Number.isNaN(raw)) {
    return 0;
  }
  const normalized = raw <= 1 ? raw * 100 : raw;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function cultureFitPercent(candidate: JobMatchCandidate, isFastProfile: boolean): number | null {
  if (isFastProfile) {
    return null;
  }
  const confidencePack =
    candidate.agent_scores && typeof candidate.agent_scores.confidence === "object" && !Array.isArray(candidate.agent_scores.confidence)
      ? (candidate.agent_scores.confidence as Record<string, unknown>)
      : null;
  const value = confidencePack?.culture ?? candidate.agent_scores.culture;
  if (typeof value !== "number" || Number.isNaN(value)) {
    return null;
  }
  return scoreToPercent(value);
}

function stateLabel(score: number): "Stable" | "Risk" {
  return score >= 70 ? "Stable" : "Risk";
}

function formatExperienceYears(years: number | undefined): string {
  if (typeof years !== "number" || Number.isNaN(years)) {
    return "Experience not provided";
  }
  const rounded = Number.isInteger(years) ? years.toFixed(0) : years.toFixed(1);
  return `${rounded} years`;
}

export default function CandidateCard({ candidate, onOpen }: CandidateCardProps) {
  const score = scoreToPercent(candidate.score);
  const skillCoverage = scoreToPercent(candidate.skill_overlap);
  const experienceFit = scoreToPercent(candidate.score_detail.experience_fit);
  const isFastProfile = isFastProfileCandidate(candidate);
  const cultureFit = cultureFitPercent(candidate, isFastProfile);
  const riskState = stateLabel(score);

  const role = candidate.seniority_level || candidate.category || "Generalist";
  const years = formatExperienceYears(candidate.experience_years);

  return (
    <article className="candidate-card" aria-label={`Candidate ${candidate.candidate_id}`}>
      <button
        type="button"
        className="candidate-card__button"
        onClick={() => onOpen(candidate)}
        aria-label={`Open details for ${candidate.candidate_id}`}
      >
        <div className="candidate-topline">
          <div>
            <h3>
              <span className="candidate-id-label">ID </span>
              {candidate.candidate_id}
            </h3>
            <p>{role}</p>
          </div>
          <MatchScorePill score={score} scoreKind={isFastProfile ? "profile" : "agent"} />
        </div>

        <div className="candidate-meta">
          <span>{years}</span>
          <span className={`status-tag status-tag--${riskState.toLowerCase()}`}>{riskState}</span>
        </div>

        <div className="subscore-grid">
          <div>
            <span>Skill Coverage</span>
            <strong>{skillCoverage}</strong>
            <div className="subscore-track"><div style={{ width: `${skillCoverage}%` }} /></div>
          </div>
          <div>
            <span>Experience Fit</span>
            <strong>{experienceFit}</strong>
            <div className="subscore-track"><div style={{ width: `${experienceFit}%` }} /></div>
          </div>
          <div>
            <span>Culture Fit</span>
            <strong>{cultureFit === null ? "N/A" : cultureFit}</strong>
            <div className="subscore-track"><div style={{ width: `${cultureFit ?? 0}%` }} /></div>
          </div>
        </div>
      </button>
    </article>
  );
}
