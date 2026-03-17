# Eval 배치 처리, LLM-as-Judge, Continuous Eval 요약

## 1. Eval 배치 처리 (Batch Evaluation)

### 진입점

| 용도 | 명령 / 스크립트 | 비고 |
|------|-----------------|------|
| 전체 파이프라인 평가 | `scripts/run_eval.sh` 또는 `python3 -m eval.eval_runner --golden-set ...` | 로컬/수동 배치 |
| LLM Judge 어노테이션 생성 | `python3 -m eval.generate_llm_judge_annotations ...` | Judge 입력 생성 선행 |

### 환경 변수 (run_eval.sh)

- `GOLDEN_SET`: 골든셋 경로 (기본 `src/eval/golden_set.jsonl`)
- `EVAL_MODE`: `full` | `hybrid` | `rerank` | `agent`
- `RUN_LABEL`: 런 라벨 (기본 `manual`)
- `OUTPUTS_DIR`: 결과 디렉터리 (기본 `src/eval/outputs`)

### Eval 모드 (config.py)

- **full**: Query understanding + Retrieval + Rerank + Agent + Performance, Human/LLM Judge agreement
- **hybrid**: Retrieval + Query understanding만 (rerank/agent 끔)
- **rerank**: Retrieval + Rerank 메트릭, agent 끔
- **agent**: Agent 평가 + Performance 중심

### 배치 처리 흐름 (eval_runner)

1. 골든셋 JSONL 로드
2. Human / LLM Judge reference 로드 (optional)
3. Rerank 실행 여부 결정 (gate)
4. **쿼리 단위 순차**: 각 row에 대해
   - Query understanding → Retrieval → (Rerank) → Agent → 메트릭 수집
5. 메트릭 집계 후 JSON/MD 리포트 출력

- Agent 평가 시 **동시 실행**: `run_candidate_tasks_with_isolation`(ThreadPool, `max_workers=10`)으로 후보별 평가 병렬화 (`matching/evaluation.py`, `matching_service.py`).

### 출력 아티팩트

- `retrieval_eval.json`, `rerank_eval.json`, `agent_eval.json`, `performance_eval.json`
- `final_eval_report.md`, `rerank_gate_state.json`

---

## 2. LLM-as-Judge

### 역할

- **Top-1 관련성**: `top1_is_relevant` (boolean)
- **설명 품질**: `explanation_quality` (overall_score, groundedness_score, coverage_score, specificity_score, pass, rationale)

Golden truth 대체가 아니라 **보조 지표**로 사용 (RESULTS.md 정책).

### 설계 문서

- [docs/evaluation/llm_judge_design.md](llm_judge_design.md)

### 생성 루프 (generate_llm_judge_annotations.py)

1. `golden.agent.jsonl` (또는 지정 subset) 로드
2. 쿼리별로 현재 agent 경로 실행 → Top-1 후보 스냅샷 수집
3. **Live Judge**: Judge 모델에 job/candidate/explanation 넘겨 JSON 응답 수집
4. Live 실패 시 **Bootstrap heuristic** fallback (token overlap, groundedness/consistency 휴리스틱)
5. `query_id` + `candidate_id` + `stage`(agent_top1) 단위로 JSONL 한 줄씩 기록

### Judge 모드

- `--judge-mode llm`: Live LLM 호출 (기본)
- Bootstrap 시 `judge_source = bootstrap_heuristic`, 설명 품질은 휴리스틱으로 계산

### Eval 연동

- `llm_judge_path`로 JSONL 로드 후:
  - `llm_as_judge_agreement`: 예측 top1 vs judge의 `top1_is_relevant` 일치율
  - `llm_explanation_quality_score` / `llm_explanation_groundedness_score`: 후보별 스코어 집계

---

## 3. Continuous Eval (지속 평가)

### 현재 구현

| 구분 | 트리거 | 워크플로 | 비고 |
|------|--------|----------|------|
| **Retrieval 벤치마크** | 매주 월요일 01:00 UTC, 또는 main push (경로 필터) | `.github/workflows/retrieval-benchmark-archive.yml` | `scripts/generate_retrieval_benchmark_archive.py` 실행, 결과를 `docs/eval/`에 커밋 |
| **Eval 아카이브** | main push (eval 등 경로 변경 시) 또는 수동 | `.github/workflows/eval-archive.yml` | `scripts/generate_eval_results.py` → `docs/eval/eval-results.md` 갱신 |

- **전체 eval_runner**를 주기적으로 돌리는 스케줄/워크플로는 없음. 권고만 있음.

### 권고 (final_eval_report.md / eval_runner)

- “Run eval_runner on a schedule and enforce calibrated thresholds for **Recall@20**, **NDCG@5**, and **degraded-mode success rate**.”
- 즉, 스케줄 배치 + 임계값으로 회귀 방지하는 형태의 continuous eval을 권장.

### Continuous Eval 확장 시 참고

1. **스케줄**: GitHub Actions `schedule`(cron) 또는 외부 스케줄러로 `scripts/run_eval.sh` (또는 `eval.eval_runner`) 주기 실행
2. **임계값**: Recall@20, NDCG@5, degraded-mode 성공률 등 메트릭을 JSON에서 읽어 fail 빌드/알림
3. **Judge**: LLM Judge는 비용/지연 때문에 매 스케줄마다 돌리기보다, 주기적 재생성(`generate_llm_judge_annotations`) 후 eval_runner에서 참조하는 방식 유지
4. **아티팩트**: 실행 시점/커밋 기준 버전·설정 스냅샷 저장해 재현성 확보 (현재 `run_id`, 출력 경로 구조 활용 가능)

---

## 4. 빠른 참조

| 항목 | 위치 |
|------|------|
| Eval 실행 | `scripts/run_eval.sh`, `src/eval/eval_runner.py` |
| Eval 설정/모드 | `src/eval/config.py` |
| 메트릭 정의 | `src/eval/metrics.py` |
| LLM Judge 생성 | `src/eval/generate_llm_judge_annotations.py` |
| Judge 설계 | `docs/evaluation/llm_judge_design.md` |
| 평가 계획 | `docs/evaluation/evaluation_plan.md` |
| 현재 결론/룰 | `src/eval/RESULTS.md`, `src/eval/README.md` |
| CI 스케줄/아카이브 | `.github/workflows/retrieval-benchmark-archive.yml`, `.github/workflows/eval-archive.yml` |
