# Next Sprint Checklist (2026-03-17)

## Must Do

- [ ] compare `agent_eval_top_n=4` vs `5` under the same prompt version
- [ ] persist runtime-mode breakdown in eval artifacts
- [ ] run `LLM-as-Judge` generation on the next agent subset and archive the output
- [ ] document whether prompt v4 explanation format should ship to production

## Should Do

- [ ] improve explanation presence without evaluating all top-10 candidates
- [ ] add retry/backoff protection around judge generation and batch eval runs
- [ ] replace heuristic token estimates with exact token accounting

## Later

- [ ] revisit `sdk_handoff` only after isolating the event-loop issue
- [ ] build a reviewer-facing ROI table for retrieval vs rerank vs agent
- [ ] fix stream cache-miss ordering so UI ranking is stable
