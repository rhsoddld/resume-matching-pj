# Resume Matching Project — 종합 Audit Report

> 기준일: 2026-03-15 | 검토 범위: requirements / PLAN / AGENT / TRACEABILITY / DESIGN_DECISION_MATRIX / README / 실코드 구조 / eval 결과

---

## 1. 전체 완성도 요약

| 레이어 | requirements ID | 문서 상태 | 코드 존재 여부 | 정합성 판정 |
|--------|----------------|-----------|---------------|------------|
| Offline Ingestion | PO.4, R1.7, DS.1-5 | Implemented | `src/backend/services/ingest_resumes.py` (45KB) | ✅ 정합 — PDF Partial |
| Query Understanding | KC.1, R1.4, R1.6 | Implemented v3 | `job_profile_extractor.py` (23KB) | ✅ 정합 |
| Hybrid Retrieval | HCR.1-2, R1.1-2 | Implemented v2 | `hybrid_retriever.py` | ✅ 정합 |
| Rerank | HCR.3, R2.3 | Partial (baseline) | `cross_encoder_rerank_service.py` (9KB) | ✅ 정합 — fine-tuning deferred |
| Multi-Agent Eval | MSA.1-6, KC.3-5 | Partial | contracts/4파일 + runtime/service.py | ⚠️ MSA.1 handoff-native 미완 |
| Weight Negotiation | AHI.5, MSA.1 | Implemented (SDK+fallback) | `sdk_runner.py` (10KB) | ✅ 정합 |
| Explainable Output | AHI.1, KC.6-7 | Implemented v3 | `match_result_builder.py` (15KB), Frontend | ✅ 정합 |
| DeepEval / LLM-Judge | R2.1, R2.2, R2.4 | Implemented | `src/eval/` 7파일 + `docs/eval/` | ⚠️ 결과 수치 이슈 (아래 참고) |
| Bias Guardrails | R2.7 | Implemented v1 | `matching_service.py`, `test_matching_service_fairness.py` | ✅ 정합 — 대시보드 Resolved (LangSmith) |
| Frontend UI | R2.8 | Implemented | `src/frontend/` | ✅ 정합 |
| Performance Benchmark | R2.6 | Partial | `benchmark_retrieval.py` | 🔴 현재 수치 불량 (아래) |
| Token Optimization | R2.5 | Planned | — | ❌ 코드 없음 |
| Feedback Loop | AHI.2 | Backlog | — | ❌ 작업 연기 |
| Analytics Dashboard | AHI.3 | Resolved | — | ✅ LangSmith 활용 |
| Interview Scheduling | AHI.4 | Backlog | — | ❌ 작업 연기 |
| Architecture JPEG/PDF | D.1 | Partial | `docs/architecture/system-architecture.md` | ⚠️ 이미지 파일 없음 |
| 발표자료 | D.4 | Planned | — | ❌ 슬라이드 없음 |

---

## 2. 문서 ↔ 코드 정합성 세부 체크

### ✅ 정합하는 항목

- **AGENT.md Query Understanding 계약 필드** (18개) → `job_profile_extractor.py` 출력 필드와 1:1 매핑 확인됨
- **DESIGN_DECISION_MATRIX 스코어 공식** `0.42*sem + 0.33*skill + 0.18*exp + 0.07*sen` → `scoring_service.py` 에 존재
- **README 현재 구현 상태 표** ↔ TRACEABILITY 상태 표기가 동일한 `Implemented/Partial/Planned` 기준 사용 (PLAN.md 완료 기준 4번 충족)
- **TRACEABILITY 증거 경로** → 실제 파일 모두 존재 (`tests/` 12개, `src/backend/` 구조 일치)
- **retrieval-benchmark** 스크립트/자동화 경로 → README 커맨드와 일치

### ⚠️ 부분 불일치 / 주의 항목

| 항목 | 문서 기술 | 실제 상태 | 갭 |
|------|-----------|-----------|-----|
| MSA.1 SDK handoff | "4-agent 실행 경로 handoff-native 확장 예정" (PLAN in_progress) | `sdk_runner.py`에 negotiation handoff만 존재. 4개 eval agent는 `service.py`의 hybrid runtime | handoff-native 전환 미완 |
| R2.3 fine-tuned embedding | "intentionally deferred" | `cross_encoder_rerank_service.py` 존재이나 fine-tuning 학습/A-B/rollback 증거 없음 | TRACEABILITY Gap에 명시 — OK |
| retrieval-benchmark 수치 | README "success_rate=1.0, candidates/sec=72.78" | 최신 `retrieval-benchmark.md` = **success_rate=0.0, 30/30 실패** | 🔴 인프라(Milvus/Mongo) 미실행 상태에서 측정된 수치. README 수치는 이전 실행 baseline |
| LLM rerank 결론 | "optional 경로 유지" | `llm-rerank-comparison.md`: delta=-0.046, 5/5 reorder | ✅ 문서 결론과 일치 |

### ❌ 문서에 없거나 코드만 있는 항목

- `src/ops/` 디렉터리(middleware, logging) → TRACEABILITY AHI.5 증거로 참조되나, Ops layer에 대한 독립 문서 없음
- `.github/workflows/eval-archive.yml`, `retrieval-benchmark-archive.yml` → README에 언급되나 workflow YAML 검증 미확인

---

## 3. 모델 성능 평가 — 현재 수치 해석

### 3-1. Custom Eval (Skill / Experience / Culture / Potential)

| Label | Skill | Experience | Culture | Potential | Quality |
|-------|-------|-----------|---------|-----------|---------|
| good (n=12) | **0.955** | 0.793 | **1.000** | **1.000** | **0.920** |
| neutral (n=1) | 0.400 | 0.875 | 0.667 | **0.000** | 0.556 |
| bad (n=2) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

**해석:**
- `good` 레이블에서 skill·culture·potential 점수가 매우 높아 golden set이 시스템과 잘 정렬되어 있음
- `neutral` 케이스의 potential=0.0 은 주의 신호 — 해당 케이스 텍스트를 직접 확인 필요
- golden set이 `good:neutral:bad = 12:1:2` 로 **good 편향**이 강함 → 실제 false positive 탐지력 검증이 부족

### 3-2. Diversity Report

| 항목 | 수치 |
|------|------|
| total_entries | 15 |
| family_count | 8 |
| family_entropy_normalized | **0.974** (매우 균등) |
| skill_vocabulary_size | 81 |

**해석:** 직군 다양성(entropy 0.97)은 매우 양호. 다만 golden set 총 15건은 통계적으로 소규모 — 50건 이상으로 확장 권장.

### 3-3. LLM-as-Judge (Rubric 기반)

| 항목 | 수치 |
|------|------|
| model | gpt-4o |
| sample_size | **3** (매우 작음) |
| average_score | **0.384** |
| score 범위 | 0.286 ~ 0.450 |

**해석:**
- rubric 기준으로 0.384는 **"Weak" 구간 (0.40~0.59 미만)** — 현재 시스템이 soft skill / potential evidence를 설득력 있게 생성하지 못함
- 특히 gs-001(0.286)은 rubric Hard Rule인 "evidence missing → ≤0.40" 경계에 해당
- sample_size=3은 신뢰하기 어려운 수치. 최소 10~15건 이상으로 확대 필요

> [!WARNING]
> LLM-as-judge 평균 **0.384**는 rubric 기준 "Poor~Weak" 경계 구간입니다. 이는 현재 후보 설명(evidence text)의 품질이 낮거나, rubric이 현재 데이터셋에 비해 너무 엄격할 수 있습니다. 원인 분석이 필요합니다.

### 3-4. Retrieval Benchmark (R2.6)

| 항목 | 최신 수치 | 이전 baseline |
|------|-----------|--------------|
| success_rate | **0.0** | 1.0 |
| candidates/sec | 0.0 | 72.8 |
| 에러 원인 | `ExternalDependencyError: Both vector retrieval and Mongo fallback failed` | — |

> [!CAUTION]
> 현재 retrieval-benchmark.md의 수치는 **Milvus + MongoDB가 Docker Compose로 실행되지 않은 상태**에서 측정된 결과입니다. `docker compose up -d`로 인프라를 올린 뒤 재실행해야 실제 성능을 확인할 수 있습니다.

### 3-5. LLM Rerank 비교 (HCR.3)

| 항목 | 수치 |
|------|------|
| Baseline avg overlap@k | 0.3774 |
| LLM rerank avg overlap@k | 0.3312 |
| **Delta** | **-0.046 (악화)** |
| 평균 latency | 3344ms |
| 순서 변경 케이스 | 5/5 |

**해석:** LLM rerank가 5건 모두 순서를 바꿨지만 proxy skill overlap 점수는 오히려 낮아짐. 이는 두 가지를 의미합니다:
1. LLM이 skill overlap 외 다른 기준(soft skill, context fit)으로 rerank하고 있을 수 있음
2. proxy metric(skill overlap)이 actual relevance를 충분히 반영하지 못할 수 있음
→ **optional 경로 유지는 합리적인 결정**이나, 실제 사람 평가(human eval) 또는 더 정밀한 proxy metric 도입이 필요

---

## 4. 남은 과제 — 우선순위별 정리

### 🔴 Critical (발표/제출 전 필수)

| 과제 | requirements ID | 현재 상태 | 예상 작업 |
|------|----------------|-----------|-----------|
| 아키텍처 다이어그램 JPEG/PDF | D.1 | Partial | README mermaid → draw.io/PNG 출력 |
| 발표 슬라이드 (10분) | D.4 | Planned | 데모 스크립트 + 8분 흐름 설계 |
| Retrieval benchmark 재실행 (인프라 UP 상태) | R2.6 | 불량 수치 | `docker compose up` 후 재측정 |
| LLM-as-Judge sample 확대 (3→15건) | R2.4 | 소규모 | `generate_eval_results.py` 재실행 |

### 🟡 Important (품질 향상)

| 과제 | requirements ID | 현재 상태 | 예상 작업 |
|------|----------------|-----------|-----------|
| 4-agent SDK handoff-native 확장 | MSA.1 | in_progress | `sdk_runner.py` 확장 |
| LLM-as-Judge 점수 개선 | R2.4 | avg 0.384 | evidence text 생성 방식 개선 or rubric 재보정 |
| Token 예산/캐시/배치 전략 | R2.5 | Planned | `matching_service.py` 개선 |
| Golden set 확대 (15→50건) | R2.1 | 소규모 | `golden_set.jsonl` 추가 작성 |

### 🟢 Nice-to-have (사후)

| 과제 | requirements ID | 현재 상태 |
|------|----------------|-----------|
| Recruiter feedback loop | AHI.2 | Backlog |
| Hiring analytics dashboard | AHI.3 | Resolved (LangSmith) |
| Interview scheduling handoff | AHI.4 | Backlog |
| Fairness metric 대시보드 | R2.7 | Resolved (LangSmith) |
| PDF 파서 보강 | PO.4, DS.3 | Partial |

---

## 5. 모델 성능 개선 방향

### 5-1. LLM-as-Judge 점수 개선 (0.384 → 0.70+ 목표)

현재 문제점과 해결책:

```
문제: candidate evidence text가 generic하거나 짧아 rubric "Evidence Quality" 차원에서 낮은 점수
해결책:
  A) match_result_builder.py에서 evidence sentence를 더 구체적으로 생성
     - 경력 기간 + 구체적 프로젝트명 + 성과 수치 포함
  B) 또는 rubric threshold 재보정 (현재 데이터가 이력서 원문 기반이라 soft skill 증거가 빈약)
  C) golden set에 더 다양한 evidence 유형(portfolio 링크, 프로젝트 설명 등) 추가
```

### 5-2. Retrieval 품질 개선 (HCR.1-3)

```
현재: baseline overlap@k = 0.377 (약 38% skill match)
목표: overlap@k ≥ 0.50

개선 경로:
  1. Hybrid fusion weight 튜닝 (vector:keyword = 현재 비율 조정)
     - 직군마다 다른 weight profile 실험 (BL-02, BL-03)
  2. Golden set 기반 오프라인 precision@k / recall@k 측정 도입
  3. BM25 skill 검색의 field weight 조정 (category, skills vs resume_text)
```

### 5-3. 에이전트 평가 일관성 (MSA.3-6)

```
현재: SDK/live/heuristic 3경로 fallback → 실행 경로에 따라 점수 분산 가능성
개선:
  1. 모든 live 실행에서 동일한 prompt + structured output 확보
  2. agent별 점수 분포를 eval suite에 추가
  3. SDK trace (LangSmith Waterfall - 첨부 이미지 참고)에서 각 agent latency 모니터링
```

### 5-4. LLM Rerank 타당성 (HCR.3)

```
현재: proxy metric 기준 -0.046 (악화), latency 3.3초
선택지:
  A) 현재처럼 optional 유지 (권장 — 문서 결론과 일치)
  B) 더 나은 proxy metric 도입 (human eval label or semantic similarity to JD)
  C) rerank 후 human annotation을 통한 실제 relevance gain 측정 (중장기)
```

---

## 6. 첨부 이미지 분석 — LangSmith Waterfall Trace

![LangSmith Waterfall Trace](/Users/lee/.gemini/antigravity/brain/f433bac6-5d4d-49e3-8548-e306e9e6ec2f/uploaded_media_1773571317145.png)

**trace 구조 해석:**

| 단계 | 시간 | 의미 |
|------|------|------|
| ChatOpenAI (최상위) | 8.34s | 전체 파이프라인 첫 번째 후보 처리 |
| agents.run_for_candidate | 12.90s | 후보별 에이전트 실행 총 시간 |
| agents.execute_runtime | 12.90s | runtime dispatch |
| Agent workflow | 4.26s | 실제 workflow 수행 |
| **SkillEvalAgent** | 4.26s | 스킬 평가 에이전트 |
| SkillEvalAgent Response | 4.25s | 응답 생성 |
| ChatOpenAI (중간) | 8.63s | 두 번째 후보 처리 |

**패턴 분석:**
- 후보 1건당 ChatOpenAI: ~7~9초, 전체는 순차 실행 패턴(cascade)
- 현재 trace에서는 **SkillEvalAgent만 보임** — Experience/Technical/Culture agent가 한 번에 보이지 않음 → heuristic fallback이 작동 중이거나 SDK path가 아직 sequential인 것으로 보임
- RERANK_GATE_MAX_TOP_N=8 설정 시 최대 8명 × ~8초 = 약 64초 소요 → R2.5 token optimization 필요성 확인
- `agents.run_for_candidate` → `agents.execute_runtime` → `Agent workflow` → `SkillEvalAgent` 4단계 nested span은 LangSmith observability가 정상 작동하고 있음을 보여줌

---

## 7. PLAN.md 완료 기준 달성 현황

| 완료 기준 | 달성 여부 |
|-----------|-----------|
| 1. 모든 requirements ID가 TRACEABILITY에 증거 링크 | ✅ (Planned 항목은 PLAN.md 참조) |
| 2. R1.9, R2.5~R2.6, AHI.2~AHI.4가 Partial 이상 | ⚠️ R2.5·AHI.2~4 여전히 Planned |
| 3. 최소 1회 eval 결과 → docs/eval/eval-results.md | ✅ 기록됨 (2026-03-15) |
| 4. README/AGENT/TRACEABILITY/ADR 상태 표기 일관 | ✅ 동일 기준 사용 |
| 5. D.1(아키텍처 이미지), D.4(발표자료) 준비 | ❌ 미완 |
