import { useMemo, useState } from "react";
import { matchCandidates } from "./api/match";
import CandidateDetailModal from "./components/CandidateDetailModal";
import CandidateResults from "./components/CandidateResults";
import JobRequirementForm from "./components/JobRequirementForm";
import RecruiterHero from "./components/RecruiterHero";
import type { JobMatchCandidate, JobMatchRequest } from "./types";

export default function App() {
  const [candidates, setCandidates] = useState<JobMatchCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<JobMatchCandidate | null>(null);

  const liveMessage = useMemo(() => {
    if (isLoading) {
      return "Searching and reranking candidates now.";
    }
    if (!hasSearched) {
      return "Ready to search candidates.";
    }
    return `${candidates.length} candidates ranked.`;
  }, [candidates.length, hasSearched, isLoading]);

  async function onSubmit(request: JobMatchRequest) {
    setIsLoading(true);
    setHasSearched(true);
    setError(null);
    setSelectedCandidate(null);

    try {
      const response = await matchCandidates(request);
      setCandidates(response.matches);
    } catch (submissionError) {
      setCandidates([]);
      setError(submissionError instanceof Error ? submissionError.message : "Search failed.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="dashboard-app">
      <RecruiterHero />

      <main className="dashboard-shell">
        <p className="sr-only" aria-live="polite">{liveMessage}</p>

        <JobRequirementForm onSubmit={onSubmit} isLoading={isLoading} />

        {error && (
          <div className="error-box" role="alert">
            {error}
          </div>
        )}

        {!hasSearched && !isLoading && (
          <section className="welcome-panel" aria-label="Dashboard guide">
            <h2>How This Dashboard Works</h2>
            <p>JD를 입력하고 필터를 설정하면 AI가 후보를 분석하고 점수와 근거를 제공합니다.</p>
          </section>
        )}

        {isLoading && (
          <section className="loading-grid" aria-label="Loading candidates">
            {Array.from({ length: 6 }).map((_, index) => (
              <div key={`loading-${index}`} className="loading-card" />
            ))}
          </section>
        )}

        {!isLoading && hasSearched && (
          <CandidateResults candidates={candidates} onOpenDetail={setSelectedCandidate} />
        )}
      </main>

      <CandidateDetailModal candidate={selectedCandidate} onClose={() => setSelectedCandidate(null)} />
    </div>
  );
}
