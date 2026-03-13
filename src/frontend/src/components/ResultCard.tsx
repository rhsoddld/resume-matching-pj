import { useState } from "react";
import type { JobMatchCandidate } from "../types";

interface Props {
  candidate: JobMatchCandidate;
  rank: number;
}

function ScoreBar({ value, label }: { value: number; label: string }) {
  const pct = Math.round(value * 100);
  return (
    <div className="score-bar-row">
      <span className="score-label">{label}</span>
      <div className="score-bar-track">
        <div className="score-bar-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="score-pct">{pct}%</span>
    </div>
  );
}

export default function ResultCard({ candidate, rank }: Props) {
  const [expanded, setExpanded] = useState(false);
  const score = candidate.score;
  const pct = Math.round(score * 100);

  // Determine badge colour based on score
  const badgeClass = pct >= 70 ? "badge-good" : pct >= 45 ? "badge-mid" : "badge-low";

  const agentScoreEntries = Object.entries(candidate.agent_scores ?? {});
  const topSkills = (candidate.core_skills?.length
    ? candidate.core_skills
    : candidate.normalized_skills
  ).slice(0, 8);

  return (
    <article className="result-card" onClick={() => setExpanded((v) => !v)}>
      {/* ── Header ── */}
      <div className="card-header">
        <div className="rank-badge">#{rank}</div>

        <div className="card-meta">
          <div className="card-title-row">
            <span className="candidate-id">{candidate.candidate_id}</span>
            {candidate.category && (
              <span className="category-chip">{candidate.category}</span>
            )}
          </div>
          <div className="card-subtitle-row">
            {candidate.experience_years != null && (
              <span className="meta-pill">🕐 {candidate.experience_years}yr</span>
            )}
            {candidate.seniority_level && (
              <span className="meta-pill">📊 {candidate.seniority_level}</span>
            )}
          </div>
        </div>

        <div className={`score-badge ${badgeClass}`}>
          <span className="score-num">{pct}</span>
          <span className="score-denom">%</span>
        </div>
      </div>

      {/* ── Skills preview ── */}
      <div className="skills-row">
        {topSkills.map((s) => (
          <span key={s} className="skill-tag">{s}</span>
        ))}
        {topSkills.length === 0 && (
          <span className="skill-tag skill-empty">No core skills</span>
        )}
      </div>

      {/* ── Expand: Score breakdown + explanation ── */}
      {expanded && (
        <div className="card-detail" onClick={(e) => e.stopPropagation()}>
          <hr className="divider" />

          {/* Score breakdown */}
          <div className="breakdown-section">
            <h4 className="section-title">Score Breakdown</h4>
            <ScoreBar value={candidate.score_detail.semantic_similarity} label="Semantic" />
            <ScoreBar value={candidate.skill_overlap} label="Skill Overlap" />
            <ScoreBar value={candidate.score_detail.experience_fit} label="Experience" />
            <ScoreBar value={candidate.score_detail.seniority_fit} label="Seniority" />
            <ScoreBar value={candidate.score_detail.category_fit} label="Category" />
            {typeof candidate.score_detail.agent_weighted === "number" && (
              <ScoreBar value={candidate.score_detail.agent_weighted} label="Agent Weighted" />
            )}
          </div>

          {/* Agent sub-scores */}
          {agentScoreEntries.length > 0 && (
            <div className="breakdown-section">
              <h4 className="section-title">Agent Scores</h4>
              {agentScoreEntries.map(([key, val]) => (
                <ScoreBar key={key} value={val} label={key} />
              ))}
            </div>
          )}

          {/* Agent explanation */}
          {candidate.agent_explanation && (
            <div className="explanation-box">
              <h4 className="section-title">AI Explanation</h4>
              <p>{candidate.agent_explanation}</p>
            </div>
          )}

          {/* Summary */}
          {candidate.summary && (
            <div className="explanation-box">
              <h4 className="section-title">Candidate Summary</h4>
              <p>{candidate.summary}</p>
            </div>
          )}
        </div>
      )}

      <div className="expand-hint">{expanded ? "▲ Collapse" : "▼ Expand details"}</div>
    </article>
  );
}
