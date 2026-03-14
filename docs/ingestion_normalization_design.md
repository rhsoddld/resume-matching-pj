# Ingestion Normalization Design

> Last updated: 2026-03-13 | Current versions: `norm-v6-substring` / `taxonomy-v5-suri`

---

## 배경: 왜 스키마를 변경했는가

- 기존 `parsed.normalized_skills` 단일 축만으로는 scoring 설명력과 ontology 추적성이 부족했다.
- 역할/버전/업무 capability 문구를 core skill과 분리해야 hybrid scoring이 안정화된다.
- 버전 메타가 없으면 Mongo/Milvus 재생성 시 어떤 기준으로 적재되었는지 추적하기 어렵다.

---

## ParsedSection 스킬 구조

`ParsedSection`의 스킬 관련 필드:

| 필드 | 의미 |
|------|------|
| `skills` | 원본 추출 skill |
| `normalized_skills` | lexical normalization 결과 |
| `canonical_skills` | alias 적용 canonical form |
| `core_skills` | taxonomy에 매핑된 scored skill |
| `expanded_skills` | taxonomy parent 확장 결과 |
| `capability_phrases` | 업무 행위/운영 문구 |
| `role_candidates` | 역할/직무 문구 |
| `review_required_skills` | 자동 판단 보류 |
| `versioned_skills` | `{raw, canonical, version}` |

---

## Ingestion 메타 버전 관리

`ingestion` 필드에 다음을 저장한다:

| 필드 | 역할 |
|------|------|
| `parsing_version` | 파서 모드 (`v4-hybrid-ontology`, `v4-structured-ontology`) |
| `normalization_version` | 정규화 계약 버전 |
| `taxonomy_version` | taxonomy 파일 버전 |
| `embedding_text_version` | embedding text 구성 버전 |
| `experience_years_method` | 경력 계산 방식 |
| `alias_applied` | alias 변환 적용 여부 |
| `taxonomy_applied` | taxonomy 매핑 적용 여부 |
| `normalization_hash` | canonical payload 기준 SHA-256 |
| `embedding_hash` | Milvus 동기화 기준 SHA-256 |
| `embedding_upserted_at` | 마지막 Milvus 반영 시각 |

---

## Experience Years 계산 방식

- 기존 단순 합산 → `month-union-v1` 방식으로 변경.
- 겹치는 경력 구간을 중복 합산하지 않는다.
- `ingestion.experience_years_method = "month-union-v1"` 기록.

---

## 운영 Ontology 파일 (runtime에서 읽는 파일)

| 파일 | 역할 |
|------|------|
| `config/skill_aliases.yml` | 동의어 → canonical 매핑 |
| `config/skill_taxonomy.yml` | core skill taxonomy |
| `config/skill_role_candidates.yml` | 역할/직무 문구 목록 |
| `config/versioned_skills.yml` | 버전이 포함된 기술 스킬 |
| `config/skill_capability_phrases.yml` | 운영/행위 문구 목록 |
| `config/skill_review_required.yml` | 리뷰 보류 목록 |

분석/이력 파일은 `docs/ontology/`에 보관한다.

---

## Normalization 이력 (Version History)

| 버전 | norm_ver | taxonomy_ver | 주요 변경 | core_skills empty | 날짜 |
|------|----------|-------------|----------|-------------------|------|
| V1 | (없음) | (없음) | 초기 단일 normalized_skills 구조 | — | — |
| V2 | `norm-v3-ontology` | `taxonomy-v2-refined` | ParsedSection 확장 (8개 스킬 필드), hash 기반 증분 처리 도입, `month-union` 경력 계산 | **55.0%** (3004/5484) | 2026-03-13 |
| V3 | `norm-v4-ontology` | `taxonomy-v3-expanded` | `skill_aliases.yml` 확장 (11개 canonical_merge: ms sql server→sql server 등), taxonomy 66→130+ 항목 (typescript, react, r 등) | **44.8%** (2459/5484) | 2026-03-13 |
| V4 | `norm-v5-category` | `taxonomy-v4-domain` | `SNEHA_CATEGORY_SKILL_MAP` (24개) 추가, Sneha category → core_skills inject, taxonomy 200+ 항목 (24개 domain) | **12.7%** (697/5484) | 2026-03-13 |
| V5 | `norm-v6-substring` | `taxonomy-v5-suri` | **Substring matching** 도입 (`sql server 2012`→`sql server`), taxonomy 260+ 항목 (Suri DBA 스킬: `database administration`, `agile`, `scrum`, `db2`, `disaster recovery` 등 65개 추가) | **0.5%** (25/5484) | 2026-03-13 |

---

## 현재 DB 스냅샷 (2026-03-13, V6 기준)

| 항목 | 값 |
|-----|-----|
| MongoDB `candidates` 총 문서 | 5,484 (Sneha 2,484 + Suri 3,000) |
| `normalization_version` | `norm-v6-substring` (전체) |
| `taxonomy_version` | `taxonomy-v5-suri` (전체) |
| `core_skills` empty | **25 / 0.5%** |
| — Sneha empty | **0 / 0.0%** |
| — Suri empty | **25 / 0.8%** (수용) |
| `taxonomy_applied=True` | 4,489 / 81.9% |
| `alias_applied=True` | 648 / 11.8% |
| `embedding_hash` | `null = 0` (Milvus 적재 완료) |
| `embedding_upserted_at` | `null = 0` |

> **Note**: 잔여 25건은 proprietary tool / 판단 불가 토큰으로, 수용 가능한 노이즈이다.

---

## Clean Rebuild 순서 (버전 변경 후)

1. `candidates` 콜렉션 드롭 (`db.drop_collection('candidates')`)
2. ingestion 재실행: `PYTHONPATH=src python src/backend/services/ingest_resumes.py --source all --target mongo --parser-mode hybrid`
3. 검증: `core_skills empty` 비율 확인 (DB 툰리 스크립트)
4. Milvus 적재: `--source all --target milvus --milvus-from-mongo --force-reembed`
5. API smoke test: `POST /api/jobs/match`

---

## Config 파일 구조 (config/)

| 파일 | 역할 | Runtime 사용 |
|------|------|-------------|
| `skill_aliases.yml` | alias → canonical 매핑 (11개 merge그룹) | ✅ `skill_ontology/runtime.py` |
| `skill_taxonomy.yml` | core skill taxonomy (260+ 항목 / taxonomy-v5-suri) | ✅ `skill_ontology/runtime.py` |
| `skill_role_candidates.yml` | 역할/직위 후보 토큰 | ✅ `skill_ontology/runtime.py` |
| `skill_capability_phrases.yml` | 업무 행위/운영 문구 | ✅ `skill_ontology/runtime.py` |
| `versioned_skills.yml` | 버전 스킬 raw→canonical 매핑 | ✅ `skill_ontology/runtime.py` |
| `skill_review_required.yml` | 자동 판단 보류 토큰 | ✅ `skill_ontology/runtime.py` |

> ⚠️ `skill_taxonomy_refined.yml` 및 `skill_review_required_refined.yml`는 **2026-03-13에 삭제**되었다.
> 전자는 skill_taxonomy.yml로 통합되었고, 후자는 skill_review_required.yml의 중복이었다.

---

## Normalization Gap 현황 (Agentic AI 연계)

> **핵심 결정 (ADR-003)**: Ingestion 파싱은 LLM 사용 ❌. Null 필드는 RAG pipeline에서 raw_text 컨텍스트로 처리.

| Gap ID | 대상 | 부족한 필드 | 현재 상태 |
|--------|------|-----------|----------|
| G-01 | Sneha 일부 | `experience_years = None` | 🟢 93건 / 허용 |
| G-02 | Suri 일부 | `core_skills` empty | 🟢 **25건 / 0.8% / 허용** |
| G-04 | Suri | `category = None` | 🟡 전체 (구조적 한계) |
| G-07 | Suri | `experience_items[].description = None` | 🟡 Abilities 텍스트로 보완 |
| G-08 | Suri | `summary`가 `"{name} resume profile"` 수준 | 🟢 낮음, embedding_text로 보완 |

---

## Substring Matching 설계 (V5 도입)

Core: `skill_ontology/runtime.py` `normalize()` 함수 내 2-pass 방식.

```python
# Pass 1: exact match
core_skills_exact = {t for t in canonical_skills if t in self.core_taxonomy}

# Pass 2: taxonomy key가 token 안에 포함되는 경우
# 조건: taxonomy key 길이 ≥ 5 (단문자 키 오탐 방지)
for token in canonical_skills:
    best = max((k for k in self.core_taxonomy if len(k) >= 5 and k in token),
               key=len, default=None)
    if best:
        substring_hits[token] = best
```

| 입력 canonical token | substring 매핑 결과 |
|---------------------|--------------------|
| `sql server 2012` | → `sql server` |
| `oracle 11.2.0.2` | → `oracle` |
| `backup and recovery using rman` | → `backup and recovery` |
| `database administration tasks` | → `database administration` |
