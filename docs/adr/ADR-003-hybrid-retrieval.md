# ADR-003 Hybrid Retrieval

## Decision
Adopt hybrid retrieval: vector similarity + lexical skill match + metadata filtering.

## Why
- Semantic recall alone misses exact skill constraints
- Keyword-only search misses transferable relevance

## Consequences
- More tuning parameters (fusion weights, rerank gate)
- Better practical retrieval quality and reviewer explainability
