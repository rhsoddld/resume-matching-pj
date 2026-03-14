# LLM-as-Judge Rubric: Soft Skill + Potential

Purpose:
- Judge candidate soft-skill alignment and growth potential from the job description and candidate evidence text.
- Return a single score in `[0.0, 1.0]`.

Scope:
- Use only job-description requirements and provided candidate evidence.
- Do not infer from protected attributes (age, gender, race, nationality, religion, disability, marital status).

## Scoring Dimensions

1. Soft-Skill Alignment (`40%`)
- Collaboration and cross-functional communication fit.
- Ownership/accountability fit.
- Clarity and consistency of interpersonal evidence.

2. Growth Potential (`40%`)
- Learning agility (upskilling, adaptability, ability to absorb new domains).
- Leadership readiness (initiative, mentoring, influence).
- Problem-solving trajectory (increasing complexity, impact expansion).

3. Evidence Quality (`20%`)
- Specificity of evidence (concrete examples over generic claims).
- Recency/relevance to the target role context.
- Internal consistency (no contradictions).

## Score Bands

- `0.90 - 1.00` Outstanding:
  - Strong soft-skill alignment plus repeated, concrete evidence of growth potential.
  - Clear signals of ownership, collaboration, and trajectory expansion.

- `0.75 - 0.89` Strong:
  - Good alignment with moderate-to-strong potential evidence.
  - Minor gaps in specificity or recency are acceptable.

- `0.60 - 0.74` Acceptable:
  - Partial alignment and/or potential signals are present but limited.
  - Evidence is somewhat generic or incomplete.

- `0.40 - 0.59` Weak:
  - Noticeable gaps in soft-skill alignment or potential evidence.
  - Mostly generic statements without convincing examples.

- `0.00 - 0.39` Poor:
  - Missing or contradictory evidence for both soft-skill fit and potential.
  - Material mismatch with role expectations.

## Hard Rules

- If evidence is missing for both soft-skill and potential dimensions, score must be `<= 0.40`.
- If job requires strong collaboration/ownership and evidence clearly contradicts it, score must be `<= 0.50`.
- If evidence is strong but very generic, cap score at `0.74`.
- If evidence is specific, consistent, and demonstrates growth trajectory, score should be `>= 0.75`.

## Output Expectations

- Output only a numeric score in `[0.0, 1.0]` for machine evaluation.
- Internally prioritize fairness and job-relevant evidence only.
