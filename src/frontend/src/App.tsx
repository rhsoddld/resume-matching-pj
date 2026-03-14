import { useState } from "react";
import { matchCandidates } from "./api/match";
import MatchForm from "./components/MatchForm";
import ResultCard from "./components/ResultCard";
import type { JobMatchCandidate, JobMatchRequest, QueryUnderstandingProfile } from "./types";

export default function App() {
  const [results, setResults] = useState<JobMatchCandidate[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [queryProfile, setQueryProfile] = useState<QueryUnderstandingProfile | null>(null);

  async function handleSubmit(request: JobMatchRequest) {
    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const response = await matchCandidates(request);
      setQueryProfile(response.query_profile);
      setResults(response.matches);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error occurred");
      setQueryProfile(null);
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="app">
      {/* ── Hero Header ── */}
      <header className="hero">
        <div className="hero-content">
          <div className="hero-badge">AI-Powered</div>
          <h1>Resume Intelligence</h1>
          <p className="hero-sub">
            Paste a job description — our multi-agent pipeline finds the best
            matched candidates from {" "}
            <strong>5,484 resumes</strong> using semantic search + explainable scoring.
          </p>
        </div>
      </header>

      {/* ── Form ── */}
      <main className="main-content">
        <section className="form-section">
          <MatchForm onSubmit={handleSubmit} isLoading={isLoading} />
        </section>

        {/* ── Error ── */}
        {error && (
          <div className="error-banner" role="alert">
            <span className="error-icon">⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* ── Loading skeleton ── */}
        {isLoading && (
          <div className="results-section">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="result-card skeleton" />
            ))}
          </div>
        )}

        {/* ── Results ── */}
        {!isLoading && hasSearched && (
          <section className="results-section">
            {queryProfile && (
              <article className="query-profile-card">
                <div className="query-profile-header">
                  <h3>Structured Query Profile</h3>
                  <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                    <span className="query-confidence-badge">
                      Confidence {Math.round((queryProfile.confidence ?? 0) * 100)}%
                    </span>
                    {queryProfile.fallback_used && (
                      <span className="query-confidence-badge">
                        LLM Fallback Applied
                      </span>
                    )}
                  </div>
                </div>
                <div className="query-confidence-track">
                  <div
                    className="query-confidence-fill"
                    style={{ width: `${Math.round((queryProfile.confidence ?? 0) * 100)}%` }}
                  />
                </div>
                <div className="query-profile-grid">
                  <div>
                    <span className="query-key">Job Category</span>
                    <span className="query-val">{queryProfile.job_category || "Not inferred"}</span>
                  </div>
                  <div>
                    <span className="query-key">Seniority Hint</span>
                    <span className="query-val">{queryProfile.seniority_hint || "Not inferred"}</span>
                  </div>
                  <div>
                    <span className="query-key">Signal Quality</span>
                    <span className="query-val">
                      unknown ratio: {Math.round(Number(queryProfile.signal_quality?.unknown_ratio ?? 0) * 100)}%
                    </span>
                  </div>
                </div>
                {queryProfile.roles?.length > 0 && (
                  <div className="query-chip-row">
                    {queryProfile.roles.map((role) => (
                      <span key={`role-${role}`} className="query-chip query-chip-primary">
                        role: {role}
                      </span>
                    ))}
                  </div>
                )}
                <div className="query-chip-row">
                  {queryProfile.skill_signals.map((skill) => (
                    <span key={`req-${skill.name}`} className="query-chip query-chip-primary">
                      {skill.strength}: {skill.name}
                    </span>
                  ))}
                  {queryProfile.capability_signals.map((cap) => (
                    <span key={`cap-${cap.name}`} className="query-chip">
                      {cap.strength}: {cap.name}
                    </span>
                  ))}
                  {queryProfile.related_skills.map((skill) => (
                    <span key={`rel-${skill}`} className="query-chip">
                      related: {skill}
                    </span>
                  ))}
                </div>
                {queryProfile.lexical_query && (
                  <p className="query-embedding-text">
                    <strong>Lexical Query:</strong> {queryProfile.lexical_query}
                  </p>
                )}
                {queryProfile.fallback_used && (
                  <p className="query-embedding-text">
                    <strong>Fallback Reason:</strong> {queryProfile.fallback_reason || "quality gate trigger"}
                    {queryProfile.fallback_rationale ? ` · ${queryProfile.fallback_rationale}` : ""}
                  </p>
                )}
                <p className="query-embedding-text">
                  <strong>Semantic Query:</strong> {queryProfile.query_text_for_embedding}
                </p>
              </article>
            )}
            {results.length > 0 ? (
              <>
                <div className="results-header">
                  <h2>
                    Found <span className="results-count">{results.length}</span> match
                    {results.length !== 1 ? "es" : ""}
                  </h2>
                  <p className="results-hint">Click a card to see score breakdown + AI explanation</p>
                </div>
                {results.map((c, i) => (
                  <ResultCard key={c.candidate_id} candidate={c} rank={i + 1} />
                ))}
              </>
            ) : (
              <div className="empty-state">
                <span className="empty-icon">🔎</span>
                <p>No matches found. Try adjusting your filters or job description.</p>
              </div>
            )}
          </section>
        )}

        {/* ── Welcome state ── */}
        {!isLoading && !hasSearched && (
          <div className="welcome-state">
            <div className="welcome-card">
              <h3>🧠 How it works</h3>
              <ol>
                <li>Enter a job description (min. 20 characters)</li>
                <li>Optionally filter by category, seniority, or experience</li>
                <li>Our multi-agent pipeline scores each candidate across Skill, Experience, Technical, and Culture dimensions</li>
                <li>Click any result card for detailed AI explanation</li>
              </ol>
            </div>
          </div>
        )}
      </main>

      <footer className="footer">
        <p>Resume Intelligence · Phase 1 ✅ · Phase 2 ✅ · Phase 3 🔄</p>
      </footer>
    </div>
  );
}
