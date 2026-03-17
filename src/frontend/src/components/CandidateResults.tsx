import CandidateCard from "./CandidateCard";
import CandidateRow from "./CandidateRow";
import type { JobMatchCandidate } from "../types";

const DISPLAY_LIMIT = 5;

interface CandidateResultsProps {
  candidates: JobMatchCandidate[];
  onOpenDetail: (candidate: JobMatchCandidate) => void;
}

export default function CandidateResults({ candidates, onOpenDetail }: CandidateResultsProps) {
  const tableRows = candidates.slice(0, DISPLAY_LIMIT);

  if (candidates.length === 0) {
    return (
      <section className="empty-panel" aria-live="polite">
        <h2>No candidates found</h2>
        <p>Try adjusting filters or making the job description more specific.</p>
      </section>
    );
  }

  return (
    <section className="candidate-results" aria-label="Candidate results">
      <header className="results-heading">
        <h2>Candidate Results</h2>
        <p>
          {candidates.length} profile{candidates.length !== 1 ? "s" : ""} ranked by explainable match score
          {candidates.length > DISPLAY_LIMIT && (
            <span className="results-heading__sub"> (showing top {DISPLAY_LIMIT})</span>
          )}
        </p>
      </header>

      <div className="candidate-table" role="table" aria-label="Candidate summary table">
        <div className="candidate-table__head" role="row">
          <span>ID</span>
          <span>Role</span>
          <span>Experience</span>
          <span>Score</span>
        </div>
        {tableRows.map((candidate) => (
          <CandidateRow key={`row-${candidate.candidate_id}`} candidate={candidate} onOpen={onOpenDetail} />
        ))}
      </div>

      <div className="candidate-card-grid">
        {candidates.map((candidate) => (
          <CandidateCard
            key={candidate.candidate_id}
            candidate={candidate}
            onOpen={onOpenDetail}
          />
        ))}
      </div>
    </section>
  );
}
