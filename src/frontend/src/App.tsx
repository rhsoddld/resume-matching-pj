import { useMemo, useState } from "react";
import { streamMatchCandidates } from "./api/match";
import CandidateDetailModal from "./components/CandidateDetailModal";
import CandidateResults from "./components/CandidateResults";
import JobRequirementForm from "./components/JobRequirementForm";
import RecruiterHero from "./components/RecruiterHero";
import type { JobMatchCandidate, JobMatchRequest, QueryUnderstandingProfile } from "./types";

export default function App() {
  const [candidates, setCandidates] = useState<JobMatchCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<JobMatchCandidate | null>(null);
  const [lastJobDescription, setLastJobDescription] = useState("");
  const [queryProfile, setQueryProfile] = useState<QueryUnderstandingProfile | null>(null);
  const [thoughtProcess, setThoughtProcess] = useState<{agent: string, message: string} | null>(null);
  const [sessionId, setSessionId] = useState<string | undefined>(undefined);

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
    setLastJobDescription(request.job_description);
    
    setCandidates([]);
    setQueryProfile(null);
    setThoughtProcess(null);
    setSessionId(undefined);

    try {
      await streamMatchCandidates(request, (type, data) => {
        if (type === "profile") {
          setQueryProfile(data as QueryUnderstandingProfile);
        } else if (type === "session") {
          // Capture session_id for AHI.2 feedback and AHI.4 email draft
          if (data?.session_id) setSessionId(data.session_id as string);
        } else if (type === "thought_process") {
          setThoughtProcess(data as {agent: string, message: string});
        } else if (type === "candidate") {
          setCandidates((prev) => {
            const newArray = [...prev, data as JobMatchCandidate];
            return newArray.sort((a, b) => b.score - a.score);
          });
        }
      });
    } catch (submissionError) {
      setCandidates([]);
      setQueryProfile(null);
      setError(submissionError instanceof Error ? submissionError.message : "Search failed.");
    } finally {
      setIsLoading(false);
      setThoughtProcess(null);
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
            <p>Enter a job description and filters, and AI will rank candidates with scores and evidence.</p>
          </section>
        )}

        {isLoading && (
          <section className="loading-section" aria-label="Loading candidates">
            {thoughtProcess ? (
              <div className="thought-process-banner">
                <span className="live-pulse"></span>
                <span className="thought-message">{thoughtProcess.message}</span>
              </div>
            ) : (
              <div className="thought-process-banner">
                <span className="live-pulse"></span>
                <span className="thought-message">Evaluating candidate profiles...</span>
              </div>
            )}
            
            {candidates.length > 0 && (
              <CandidateResults candidates={candidates} onOpenDetail={setSelectedCandidate} />
            )}
            
            <div className="loading-grid">
              {Array.from({ length: Math.max(1, 6 - candidates.length) }).map((_, index) => (
                <div key={`loading-${index}`} className="loading-card" />
              ))}
            </div>
          </section>
        )}

        {!isLoading && hasSearched && (
          <CandidateResults candidates={candidates} onOpenDetail={setSelectedCandidate} />
        )}
      </main>

      <CandidateDetailModal
        candidate={selectedCandidate}
        queryProfile={queryProfile}
        jobDescription={lastJobDescription}
        sessionId={sessionId}
        onClose={() => setSelectedCandidate(null)}
      />
    </div>
  );
}
