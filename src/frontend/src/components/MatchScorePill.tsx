interface MatchScorePillProps {
  score: number;
  /** "profile" = profile-only score (no agent); "agent" = agent-evaluated score */
  scoreKind?: "profile" | "agent";
}

export default function MatchScorePill({ score, scoreKind = "agent" }: MatchScorePillProps) {
  const normalized = Math.max(0, Math.min(100, Math.round(score)));
  const tone = normalized >= 70 ? "good" : normalized >= 55 ? "warn" : "bad";
  const label = scoreKind === "profile" ? "Profile" : "Agent";

  return (
    <span className="match-score-pill-wrap" title={scoreKind === "profile" ? "Profile score (Agent evaluation not applied)" : "Agent score"}>
      <span className={`match-score-pill match-score-pill--${tone}`} aria-label={`${label} score ${normalized}`}>
        {normalized}
      </span>
      <span className="match-score-pill-label">{label}</span>
    </span>
  );
}
