import CandidateCard from "./CandidateCard";
import CandidateRow from "./CandidateRow";
import type { JobMatchCandidate } from "../types";

interface CandidateResultsProps {
  candidates: JobMatchCandidate[];
  onOpenDetail: (candidate: JobMatchCandidate) => void;
}

export default function CandidateResults({ candidates, onOpenDetail }: CandidateResultsProps) {
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
        <p>{candidates.length} profiles ranked by explainable match score</p>
      </header>

      <div className="candidate-table" role="table" aria-label="Candidate summary table">
        <div className="candidate-table__head" role="row">
          <span>Name</span>
          <span>Role</span>
          <span>Experience</span>
          <span>Score</span>
        </div>
        {candidates.slice(0, 6).map((candidate) => (
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
