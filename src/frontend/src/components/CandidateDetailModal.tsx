import { useEffect, useMemo } from "react";
import type { JobMatchCandidate } from "../types";
import BiasGuardrailBanner from "./BiasGuardrailBanner";
import ExplainabilityPanel from "./ExplainabilityPanel";

interface CandidateDetailModalProps {
  candidate: JobMatchCandidate | null;
  onClose: () => void;
}

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

function confidenceFrom(value: unknown): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return 0;
  }
  const normalized = value <= 1 ? value * 100 : value;
  return Math.max(0, Math.min(100, Math.round(normalized)));
}

const AGENT_SECTIONS: Array<{ key: string; label: string }> = [
  { key: "parsing", label: "Parsing" },
  { key: "skill", label: "Skill" },
  { key: "experience", label: "Experience" },
  { key: "technical", label: "Technical" },
  { key: "culture", label: "Culture" },
];

export default function CandidateDetailModal({ candidate, onClose }: CandidateDetailModalProps) {
  const warnings = useMemo(() => {
    if (!candidate) {
      return [];
    }

    const list: string[] = [...(candidate.bias_warnings ?? [])];
    if ((candidate.possible_gaps?.length ?? 0) > 2) {
      list.push("Several potential skill gaps were detected. Validate job-critical requirements manually.");
    }
    if (confidenceFrom(candidate.agent_scores.culture) < 40) {
      list.push("Culture-fit confidence is low. Use structured interviews before making decisions.");
    }
    return Array.from(new Set(list));
  }, [candidate]);

  useEffect(() => {
    if (!candidate) {
      return undefined;
    }

    function onKeydown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        onClose();
      }
    }

    window.addEventListener("keydown", onKeydown);
    return () => {
      window.removeEventListener("keydown", onKeydown);
    };
  }, [candidate, onClose]);

  if (!candidate) {
    return null;
  }

  return (
    <div
      className="candidate-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Candidate detail modal"
      onClick={onClose}
    >
      <div className="candidate-modal" onClick={(event) => event.stopPropagation()}>
        <header className="candidate-modal__header">
          <div>
            <h2>{candidate.candidate_id}</h2>
            <p>{candidate.seniority_level || candidate.category || "Candidate profile"}</p>
          </div>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close details">
            Close
          </button>
        </header>

        <BiasGuardrailBanner warnings={warnings} />

        <div className="candidate-modal__body">
          <section className="candidate-modal__left">
            <article className="detail-panel">
              <h3>Summary</h3>
              <p>{candidate.summary ?? "No summary provided."}</p>
            </article>

            <article className="detail-panel">
              <h3>Key Experience</h3>
              <ul>
                {(candidate.relevant_experience ?? []).slice(0, 6).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </article>

            <article className="detail-panel">
              <h3>Projects / Signals</h3>
              <div className="chip-list">
                {candidate.core_skills.slice(0, 10).map((skill) => (
                  <span className="chip" key={skill}>{skill}</span>
                ))}
              </div>
            </article>
          </section>

          <aside className="candidate-modal__right">
            <ExplainabilityPanel candidate={candidate} />

            <section className="agent-eval-panel" aria-label="AI evaluation panel">
              <h3>Multi-agent Evaluation</h3>
              <div className="agent-list">
                {AGENT_SECTIONS.map((section) => {
                  const confidencePack = toRecord(candidate.agent_scores.confidence);
                  const confidence = confidenceFrom(confidencePack?.[section.key] ?? candidate.agent_scores[section.key]);
                  const evidencePack = toRecord(candidate.agent_scores.evidence);
                  const evidenceList = evidencePack?.[section.key];
                  const evidenceText = Array.isArray(evidenceList) && evidenceList.length > 0
                    ? String(evidenceList[0])
                    : (confidence >= 60 ? "Strong signal from profile content" : "Limited explicit evidence");
                  return (
                    <article key={section.key} className="agent-card">
                      <div>
                        <strong>{section.label}</strong>
                        <p>Confidence {confidence}%</p>
                      </div>
                      <p className="agent-evidence">Evidence: {evidenceText}</p>
                    </article>
                  );
                })}
              </div>
            </section>
          </aside>
        </div>
      </div>
    </div>
  );
}
