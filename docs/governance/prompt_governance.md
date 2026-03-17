# Prompt Governance

## Prompt Ownership

| Area | Source |
|---|---|
| Agent prompts | `src/backend/agents/runtime/prompts.py` |
| Prompt version | `PROMPT_VERSION` (currently v5: reflects evidence role separation) |
| Evidence role separation (v5) | [agent_evaluation_and_scoring.md § 2.5](../agents/agent_evaluation_and_scoring.md#25-evidence-role-separation-evidence-rule-prompt-v5) |
| Judge rubric reference | `docs/evaluation/evaluation_results.md` (rubric snapshot) |

## Prompt Change Rules

1. Any prompt change must ship with a version bump.
2. Schema output contracts must be preserved across changes.
3. Add explicit rules to prevent ungrounded inference / hallucination.
4. Add explicit rules to exclude protected attributes.
5. After changes, leave at least one eval evidence artifact.

## Mandatory Audit Fields

- `prompt_version`
- `runtime_mode`
- `request_id`
- `runtime_fallback_used`
- `runtime_reason`

## Judge Rubric Guardrails (Legacy Restored)

LLM-as-Judge evaluation follows these principles.
- soft-skill alignment (40%)
- growth potential (40%)
- evidence quality (20%)

Hard rules:
1. If soft-skill/potential evidence is broadly lacking, score `<= 0.40`
2. If there is clear contradiction with collaboration/ownership expectations, score `<= 0.50`
3. Generic evidence is capped at `0.74`
4. If evidence is specific/consistent and shows growth trajectory, score `>= 0.75`

## Prompt Review Checklist

- Do input/output schemas match the documentation?
- Is there any forbidden evidence (protected attributes, fabricated claims)?
- Is the fallback reason recorded in logs and responses?
- Is the quality gain worth the cost?
