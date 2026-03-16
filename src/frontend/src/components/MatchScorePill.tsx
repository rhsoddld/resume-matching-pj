interface MatchScorePillProps {
  score: number;
}

export default function MatchScorePill({ score }: MatchScorePillProps) {
  const normalized = Math.max(0, Math.min(100, Math.round(score)));
  const tone = normalized >= 70 ? "good" : normalized >= 55 ? "warn" : "bad";

  return (
    <span className={`match-score-pill match-score-pill--${tone}`} aria-label={`Match score ${normalized}`}>
      {normalized}
    </span>
  );
}
