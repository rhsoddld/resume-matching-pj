# ADR-001 Vector DB

## Decision
Use Milvus as the primary vector retrieval store and MongoDB as the document source/fallback.

## Why
- Strong vector retrieval performance
- Metadata filtering support
- Works cleanly with Docker-based local environment

## Consequences
- Requires synchronization between document and vector stores
- Solved by coordinated ingestion upsert strategy
