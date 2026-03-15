import type { JobMatchCandidate } from "../types";
import MatchScorePill from "./MatchScorePill";

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

  return (
    <button type="button" className="candidate-row" onClick={() => onOpen(candidate)}>
      <span>{candidate.candidate_id}</span>
      <span>{candidate.category ?? "General"}</span>
      <span>{formatExperienceYears(candidate.experience_years)}</span>
      <MatchScorePill score={score} />
    </button>
  );
}
