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
        <p>필터를 조정하거나 JD를 더 구체적으로 입력해보세요.</p>
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
          <span>Years</span>
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
