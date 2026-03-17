## Requirements Checklist Verification

이 문서는 `docs/governance/TRACEABILITY.md`에서 언급하는 체크리스트/요건(R2.3, R2.5, R2.6, AHI.2–AHI.4)의 **“어디를 보면 충족을 확인할 수 있는지”**를 빠르게 찾을 수 있도록 증거 경로를 모아둡니다.

---

## R2.3 — Rerank 테스트·경로

- **스크립트**: `scripts/run_rerank_eval.sh`
- **golden subset**: `src/eval/subsets/golden.rerank.jsonl`
- **관련 문서(평가)**:
  - `docs/evaluation/evaluation_plan.md`
  - `docs/evaluation/evaluation_results.md`

---

## R2.5 — LangSmith 기반 token 관측 + 설정 기반 최적화

- **관측(Tracing)**: `langsmith` 연동 (환경 변수/설정은 `.env.example` 및 백엔드 설정 참조)
- **설정 기반 제어(예: budget/caching)**:
  - `src/backend/core/settings.py`
  - `src/backend/services/matching/cache.py`

---

## R2.6 — Throughput benchmark / 성능 근거

- **성능 결과(샘플 산출물)**: `src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4_judged/performance_eval.json`
- **아키텍처 확장성 근거(문서)**:
  - `docs/architecture/deployment_architecture.md`

---

## AHI.2–AHI.4 — Feedback / Analytics / Handoff(면접·이메일 초안)

- **API/서비스 구현 근거**:
  - `src/backend/api/`
  - `src/backend/services/`
- **전체 흐름 이해(문서)**:
  - `docs/data-flow/candidate_retrieval_flow.md`
  - `docs/data-flow/resume_ingestion_flow.md`

