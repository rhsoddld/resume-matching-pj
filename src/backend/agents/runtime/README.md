# Agent Orchestration Module Guide

This package splits candidate evaluation into small modules so each file has one clear job.

## Why this exists

The previous implementation kept SDK execution, live fallback, payload building, and heuristic scoring in one large service file.
This package keeps the public service contract stable while making internals easier to read and extend.

## Module map

- `service.py`: main orchestrator entrypoint used by `matching_service`.
- `candidate_mapper.py`: converts candidate/job data into per-agent inputs and payload.
- `sdk_runner.py`: OpenAI Agents SDK execution path.
- `live_runner.py`: single-call JSON orchestrator path.
- `heuristics.py`: deterministic fallback scoring path.
- `prompts.py`: versioned prompt registry (`PROMPT_VERSION`).
- `helpers.py`: shared scoring/weight/utility helpers.
- `models.py`, `types.py`: local data contracts for orchestration internals.

## Prompt versioning

`PROMPT_VERSION` is appended to ranking explanation output for traceability.
When prompts change, bump this version and keep behavior notes in governance docs.
