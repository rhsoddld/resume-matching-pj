# Known Trade-offs

## 1) Ingestion parsing: rule-based only (no generative parsing)
- Choice: `ingest_resumes.py` parsing is rule-based, while LLM usage is limited to embedding and later matching stages.
- Benefit: lower cost, reproducible outputs, lower operational risk for bulk ingestion.
- Trade-off: unstructured resumes can leave some structured fields empty.
- Mitigation: keep `raw.resume_text`, expand ontology config, and use fallback interpretation at matching time.

## 2) Dual store strategy: MongoDB + Milvus
- Choice: MongoDB stores domain documents; Milvus handles vector retrieval.
- Benefit: better retrieval speed/quality and cleaner separation of responsibilities.
- Trade-off: synchronization complexity across two stores.
- Mitigation: ingestion writes are designed as coordinated upserts, with hash-based incremental embedding logic.

## 3) Deterministic scoring baseline before multi-agent scoring
- Choice: current default ranking path uses deterministic score components.
- Benefit: predictable behavior, easier regression testing, clear score breakdown for reviewers.
- Trade-off: less nuanced semantic judgment than full LLM-agent reasoning.
- Mitigation: keep deterministic baseline as stable core, then layer rerank/agent scoring incrementally.

## 4) Documentation policy: as-is first, target-state separate
- Choice: README/PLAN describe current repository structure first; future structure is explicitly marked as roadmap.
- Benefit: avoids reviewer confusion and protects submission credibility.
- Trade-off: less “future vision” in the primary structure section.
- Mitigation: keep a clearly separated target-state section and ADR updates.

## 5) Embedding model baseline: `text-embedding-3-small`
- Choice: use `OPENAI_EMBEDDING_MODEL=text-embedding-3-small` as the default.
- Benefit: lower cost and faster iteration for ingestion/re-embedding cycles and capstone demos.
- Trade-off: may underperform `text-embedding-3-large` in edge semantic-retrieval cases.
- Mitigation: keep model selection configurable via environment variable and upgrade to large when quality benchmarks require it.
