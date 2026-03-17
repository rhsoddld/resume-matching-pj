# 코드·문서 정합성 체크

코드베이스와 마크다운 문서 간 일치 여부를 점검한 결과입니다. 자료 정리·최종 검토 시 참고용입니다.

**검증 일자:** 2026-03-17

---

## 1. Ignore 파일

| 파일 | 상태 | 비고 |
|------|------|------|
| **.gitignore** | ✅ 갱신됨 | Python/Node/IDE/로그/`data/`/`.env`/eval 출력(`src/eval/outputs/`) 등 반영. eval 출력은 `src/eval/outputs/` 한 줄로 통합. |
| **.dockerignore** (루트) | ✅ 유지 | `.git`, `data/`, `docs/`, `scripts/`, `src/frontend/`, `tests/` 등으로 빌드 컨텍스트 최소화. |
| **src/frontend/.dockerignore** | ✅ 유지 | `node_modules/`, `dist/` 등. |
| **.cursorignore** | 없음 | 사용하지 않음. 필요 시 `.cursorignore` 추가 가능. |

---

## 2. API 라우트 (코드 ↔ 문서)

`api_prefix = "/api"` 기준, 실제 엔드포인트와 문서 기술이 일치합니다.

| 메서드 | 경로 | 문서 기술 위치 | 일치 |
|--------|------|----------------|:----:|
| GET | `/api/health` | README, Success Criteria | ✅ |
| GET | `/api/ready` | README, Success Criteria | ✅ |
| GET | `/api/candidates/{candidate_id}` | - | ✅ |
| GET | `/api/jobs/filters` | README (JobMatchRequest, 필터) | ✅ |
| POST | `/api/jobs/match` | README, candidate_retrieval_flow, CODE_STRUCTURE | ✅ |
| POST | `/api/jobs/match/evaluate-candidate` | - | ✅ |
| POST | `/api/jobs/match/stream` | - | ✅ |
| POST | `/api/jobs/extract-pdf` | - | ✅ |
| POST | `/api/jobs/draft-interview-email` | - | ✅ |
| POST | `/api/ingestion/resumes` | resume_ingestion_flow § Ingestion API Surface | ✅ |
| POST | `/api/feedback/sessions/{session_id}/candidates/{candidate_id}` | - | ✅ |
| GET | `/api/feedback/sessions/{session_id}` | - | ✅ |

---

## 3. Ingestion API (스키마·문서)

| 항목 | 문서 (resume_ingestion_flow.md) | 코드 (schemas/ingestion.py, api/ingestion.py) | 일치 |
|------|----------------------------------|-----------------------------------------------|:----:|
| 엔드포인트 | `POST /api/ingestion/resumes` | `@router.post("/resumes")` + prefix `/api` + `/ingestion` | ✅ |
| source | `sneha \| suri \| all` | `Literal["sneha", "suri", "all"]` | ✅ |
| target | `mongo \| milvus \| all` | `Literal["all", "mongo", "milvus"]` | ✅ |
| parser_mode | `rule \| spacy \| hybrid` | `Literal["rule", "spacy", "hybrid"]` | ✅ |
| milvus_from_mongo, force_*, dry_run, async_mode 등 | 문서 명시 | `IngestionRunRequest` 필드와 동일 | ✅ |
| X-API-Key / rate limit / async 정책 | INGESTION_API_KEY, ingestion_rate_limit_per_minute, ingestion_allow_async | settings.ingestion_api_key 등으로 로드 (.env: INGESTION_*) | ✅ |

---

## 4. 경로·폴더 구조 (CODE_STRUCTURE.md ↔ 실제)

| 문서 기술 | 실제 경로 | 일치 |
|-----------|-----------|:----:|
| api: candidates, jobs, ingestion, feedback | `api/candidates.py`, `jobs.py`, `ingestion.py`, `feedback.py` | ✅ |
| core: settings, database, vector_store, filter_options, … | 존재 | ✅ |
| repositories: mongo_repo, hybrid_retriever (재export), session_repo | 존재. `repositories/hybrid_retriever.py`는 services 쪽 재export | ✅ |
| services: matching_service, hybrid_retriever, ingest_resumes, … | 목록과 실제 서비스 파일 일치 | ✅ |
| services/ingestion/, matching/, retrieval/, job_profile/, skill_ontology/ | 존재 | ✅ |
| agents/contracts/, agents/runtime/ | 존재 | ✅ |
| data-flow: resume_ingestion_flow, candidate_retrieval_flow | 존재 | ✅ |
| data-flow: test_datasets_and_commands | **추가됨** (기존 누락 문서 생성 후 CODE_STRUCTURE에 반영) | ✅ |

---

## 5. README 링크

| 링크 | 대상 파일 | 상태 |
|------|-----------|------|
| docs/data-flow/test_datasets_and_commands.md | 테스트 데이터셋·커맨드 | ✅ 생성됨, 링크 유효 |
| docs/CODE_STRUCTURE.md | 코드 구조·확장 가이드 | ✅ |
| docs/Key Design Decisions.md | 핵심 설계 결정 | ✅ |
| docs/design_rationale_ontology_eval_cost.md | 설계 근거 | ✅ |
| docs/architecture/system_architecture.md, deployment_architecture.md | 아키텍처 | ✅ |
| docs/data-flow/resume_ingestion_flow.md, candidate_retrieval_flow.md | 데이터 플로우 | ✅ |
| docs/agents/*, docs/evaluation/*, docs/governance/* 등 | 해당 문서들 | ✅ |

---

## 6. 데이터 플로우 문서 ↔ 구현

- **resume_ingestion_flow.md**  
  - 파이프라인 단계(Load → Parse → Normalize → MongoDB/Milvus), 전처리 모듈(`preprocessing.py`, `transformers.py`, `state.py`, `constants.py`), ID 정규화(sneha-*, suri-*), 스키마·운영 가드 모두 코드와 맞음.
- **candidate_retrieval_flow.md**  
  - Entry `POST /api/jobs/match`, MatchingService, HybridRetriever, cache, enrichment, rerank, agent 오케스트레이션 경로가 코드와 일치.

---

## 7. 요약

| 구분 | 결과 |
|------|------|
| Ignore 파일 | .gitignore 정리·갱신됨. .dockerignore 유지. |
| API 라우트 | 코드와 문서 일치. |
| Ingestion API | 스키마·엔드포인트·환경 변수명 문서와 일치. |
| CODE_STRUCTURE | 경로·폴더 구조 일치. data-flow에 test_datasets_and_commands.md 반영. |
| README 링크 | 누락되었던 test_datasets_and_commands.md 생성으로 모든 링크 유효. |
| 데이터 플로우 문서 | resume_ingestion_flow, candidate_retrieval_flow 모두 구현과 정합성 유지. |

**결론:** 코드와 MD 설명 간 정합성은 확보된 상태이며, ignore 파일 갱신 및 누락 문서 추가로 자료 정리·최종 체크에 사용할 수 있습니다.
