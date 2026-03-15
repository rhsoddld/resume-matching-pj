import type { JobMatchCandidate } from "../types";
import { isFastProfileCandidate } from "../utils/agentEvaluation";

interface ExplainabilityPanelProps {
  candidate: JobMatchCandidate;
}

function toPercent(value: number | undefined): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  const normalized = value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

function getCultureFit(candidate: JobMatchCandidate): number | null {
  if (isFastProfileCandidate(candidate)) {
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
  return toPercent(value);
}

export default function ExplainabilityPanel({ candidate }: ExplainabilityPanelProps) {
  const evidence = candidate.relevant_experience.slice(0, 4);
  const missing = candidate.possible_gaps.slice(0, 4);
  const transferable = candidate.expanded_skills
    .filter((skill) => !candidate.core_skills.includes(skill))
    .slice(0, 6);
  const cultureFit = getCultureFit(candidate);

  return (
    <section className="explainability-panel" aria-label="Explainable match breakdown">
      <h3>Explainable Match Breakdown</h3>
      <div className="explainability-metric-grid">
        <div>
          <span className="metric-label">Skill Coverage</span>
          <strong>{toPercent(candidate.skill_overlap)}%</strong>
        </div>
        <div>
          <span className="metric-label">Experience Fit</span>
          <strong>{toPercent(candidate.score_detail.experience_fit)}%</strong>
        </div>
        <div>
          <span className="metric-label">Culture Fit</span>
          <strong>{cultureFit === null ? "N/A" : `${cultureFit}%`}</strong>
        </div>
      </div>

      <div className="explainability-block">
        <h4>Evidence Sentences</h4>
        <ul>
          {evidence.length > 0 ? (
            evidence.map((item) => <li key={item}>{item}</li>)
          ) : (
            <li>No explicit evidence extracted.</li>
          )}
        </ul>
      </div>

      <div className="explainability-block">
        <h4>Missing Skills</h4>
        <ul>
          {missing.length > 0 ? (
            missing.map((item) => <li key={item}>{item}</li>)
          ) : (
            <li>No critical gap flagged.</li>
          )}
        </ul>
      </div>

      <div className="explainability-block">
        <h4>Transferable Skills</h4>
        <div className="chip-list">
          {transferable.length > 0 ? (
            transferable.map((skill) => (
              <span className="chip" key={skill}>
                {skill}
              </span>
            ))
          ) : (
            <span className="chip">Not available</span>
          )}
        </div>
      </div>
    </section>
  );
}
