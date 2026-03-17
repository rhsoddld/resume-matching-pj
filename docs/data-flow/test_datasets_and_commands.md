# 테스트용 데이터셋 & 커맨드

이 문서는 로컬 검증·평가에 사용하는 데이터셋 위치와 표준 커맨드를 정리합니다. Quick Start는 [README](../../README.md)를 참고하세요.

---

## 데이터셋 위치

| 소스 | 설명 | 위치 / 비고 |
|------|------|-------------|
| **Sneha** | `snehaanbhawal/resume-dataset` (Resume.csv) | 프로젝트 루트 `data/` 폴더 (CSV). limit 없으면 전체 사용. |
| **Suri** | `suriyaganesh/resume-dataset-structured` (01~05_*.csv) | 프로젝트 루트 `data/` 폴더 (CSV). **3000건** 권장·기본 예시 (`--suri-limit 3000`). |

- `data/`는 `.gitignore`에 포함되어 있어 저장소에 커밋되지 않습니다. 데이터는 별도로 다운로드하거나 준비해야 합니다.
- 상세 수집·정규화 흐름은 [resume_ingestion_flow.md](resume_ingestion_flow.md)를 참고하세요.

---

## 표준 커맨드

### Ingestion (적재)

```bash
# 1) 소스 데이터 → MongoDB (파싱·정규화) — Suri 3000건 예시
python3 scripts/ingest_resumes.py --source all --target mongo --suri-limit 3000

# 2) MongoDB 기준으로 Milvus 벡터 인덱스 생성
python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo
```

- 빠른 검증 시: `--sneha-limit 200 --suri-limit 500` 등으로 건수 조절 가능.
- 옵션 상세: `scripts/ingest_resumes.py` 및 `src/backend/services/ingest_resumes.py` 참고.

### 매칭 API 테스트

- [README — Get Recommendations (curl)](../../README.md#get-recommendations)의 curl 예시 사용.
- Health: `GET http://localhost:8000/api/health`, Ready: `GET http://localhost:8000/api/ready`.

### 평가 (Eval)

- Golden set은 `suri-*` ID 사용 → Suri 데이터 적재 필요.
- 스크립트:
  - `./scripts/run_retrieval_eval.sh`
  - `./scripts/run_eval.sh`
  - `./scripts/run_rerank_eval.sh`
  - `./scripts/update_golden_set.sh`, `./scripts/regen_golden_set.sh`

---

## 관련 문서

- [Resume Ingestion Flow](resume_ingestion_flow.md)
- [Candidate Retrieval Flow](candidate_retrieval_flow.md)
- [README — Setup & Usage](../../README.md)
