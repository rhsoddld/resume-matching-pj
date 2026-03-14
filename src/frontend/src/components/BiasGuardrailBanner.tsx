interface BiasGuardrailBannerProps {
  warnings: string[];
}

export default function BiasGuardrailBanner({ warnings }: BiasGuardrailBannerProps) {
  if (warnings.length === 0) {
    return null;
  }

  return (
    <aside className="bias-guardrail-banner" role="alert" aria-live="polite">
      <strong>Guardrail Alert</strong>
      <ul>
        {warnings.map((warning) => (
          <li key={warning}>{warning}</li>
        ))}
      </ul>
    </aside>
  );
}
