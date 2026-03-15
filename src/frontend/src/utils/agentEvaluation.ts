import type { JobMatchCandidate } from "../types";

function toRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return null;
  }
  return value as Record<string, unknown>;
}

export function isFastProfileCandidate(candidate: JobMatchCandidate): boolean {
  const agentScores = toRecord(candidate.agent_scores);
  if (!agentScores) {
    return false;
  }

  const explicitApplied = agentScores.agent_evaluation_applied;
  if (typeof explicitApplied === "boolean") {
    return !explicitApplied;
  }

  const runtimeMode = String(agentScores.runtime_mode ?? "");
  return runtimeMode === "deterministic_only";
}
