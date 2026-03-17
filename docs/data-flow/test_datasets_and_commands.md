# Test datasets & commands

This document lists dataset locations and standard commands used for local validation and evaluation. For quick start, see [README](../../README.md).

---

## Dataset locations

| Source | Description | Location / notes |
|------|------|-------------|
| **Sneha** | `snehaanbhawal/resume-dataset` (Resume.csv) | `data/` folder at the repo root (CSV). Uses full dataset unless you set a limit. |
| **Suri** | `suriyaganesh/resume-dataset-structured` (01~05_*.csv) | `data/` folder at the repo root (CSV). Recommended default example is **3000 rows** (`--suri-limit 3000`). |

- `data/` is in `.gitignore` and is not committed. You must download/prepare datasets separately.
- For ingestion/normalization details, see [resume_ingestion_flow.md](resume_ingestion_flow.md).

---

## Standard commands

### Ingestion

```bash
# 1) Source data → MongoDB (parse + normalize) — Suri 3000 example
python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000

# 2) Build Milvus vector index from MongoDB
python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo
```

- For quick smoke checks: downscale with `--sneha-limit 200 --suri-limit 500`, etc.
- For option details, see `scripts/ingest_resumes.py` and `src/backend/services/ingest_resumes.py`.

### Match API smoke test

- Use the curl examples in [README — Get Recommendations (curl)](../../README.md#get-recommendations).
- Health: `GET http://localhost:8000/api/health`, Ready: `GET http://localhost:8000/api/ready`.

### Evaluation (eval)

- The golden set uses `suri-*` IDs → requires Suri ingestion.
- Scripts:
  - `./scripts/run_retrieval_eval.sh`
  - `./scripts/run_eval.sh`
  - `./scripts/run_rerank_eval.sh`
  - `./scripts/update_golden_set.sh`, `./scripts/regen_golden_set.sh`

---

## Related docs

- [Resume Ingestion Flow](resume_ingestion_flow.md)
- [Candidate Retrieval Flow](candidate_retrieval_flow.md)
- [README — Setup & Usage](../../README.md)
