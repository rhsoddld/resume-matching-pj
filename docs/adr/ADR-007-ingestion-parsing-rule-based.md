# ADR-007 Ingestion Parsing (Rule-based, No LLM)

## Decision
Resume/candidate ingestion uses rule-based, deterministic parsing only. Do not use generative LLM for structured field extraction in the default ingestion path.

## Why
- Cost, reproducibility, and operational stability for bulk ingestion
- Avoids non-deterministic output and latency from LLM-based parsing at scale

## Consequences
- Some fields may be null or coarse for highly unstructured resumes; raw text is retained and used as RAG context in matching so retrieval can still leverage full content
- ResumeParsingAgent exists in design but is not operated; future LLM-assisted parsing would be an optional enhancement with clear scope and evaluation

*Ref:* [resume_ingestion_flow.md](../data-flow/resume_ingestion_flow.md); ingestion vs matching parsing split in [ADR-003](ADR-003-hybrid-retrieval.md) context.
