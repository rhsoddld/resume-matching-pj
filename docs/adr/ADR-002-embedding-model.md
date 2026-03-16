# ADR-002 Embedding Model

## Decision
Set `text-embedding-3-small` as the default embedding model baseline.

## Why
- Lower cost and faster indexing/re-indexing cycles
- Good enough quality baseline for capstone scope

## Consequences
- Some edge semantic cases may improve with larger models
- Keep model selection configurable for future upgrades
