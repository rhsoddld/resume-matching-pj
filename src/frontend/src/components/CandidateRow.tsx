import type { JobMatchCandidate } from "../types";
import MatchScorePill from "./MatchScorePill";
import { isFastProfileCandidate } from "../utils/agentEvaluation";

interface CandidateRowProps {
  candidate: JobMatchCandidate;
  onOpen: (candidate: JobMatchCandidate) => void;
}

function normalize(raw: number): number {
  return Math.max(0, Math.min(100, Math.round(raw <= 1 ? raw * 100 : raw)));
}

function formatExperienceYears(years: number | undefined): string {
  if (typeof years !== "number" || Number.isNaN(years)) {
    return "Not provided";
  }
  const rounded = Number.isInteger(years) ? years.toFixed(0) : years.toFixed(1);
  return `${rounded}y`;
}

export default function CandidateRow({ candidate, onOpen }: CandidateRowProps) {
  const score = normalize(candidate.score);
  const isFastProfile = isFastProfileCandidate(candidate);

  return (
    <button type="button" className="candidate-row" onClick={() => onOpen(candidate)}>
      <span>
        {candidate.candidate_id}
        {isFastProfile && <span className="fast-profile-badge fast-profile-badge--inline">Fast Profile</span>}
      </span>
      <span>{candidate.category ?? "General"}</span>
      <span>{formatExperienceYears(candidate.experience_years)}</span>
      <MatchScorePill score={score} />
    </button>
  );
}
