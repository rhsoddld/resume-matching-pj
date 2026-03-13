# Resume Ingestion & Normalization Flow

## Scope

| 항목 | 내용 |
|------|------|
| **Source datasets** | `snehaanbhawal/resume-dataset` (`Resume.csv`), `suriyaganesh/resume-dataset-structured` (`01~05_*.csv`) |
| **Target stores** | MongoDB `candidates`, Milvus `candidate_embeddings` |
| **Ingestion script** | `src/backend/services/ingest_resumes.py` |

---

## Pipeline Summary

```
Raw CSV
  ↓ 1. Load rows
  ↓ 2. Parse + normalize (regex, spaCy, dateparser)
  ↓ 3. Map → unified Candidate schema
  ↓ 4. Build embedding_text
  ↓ 5. Compute normalization_hash
  ↓ 6. Upsert changed docs only → MongoDB (--target mongo)
  ↓ 7. Embed changed docs only → Milvus (--target milvus)
```

---

## Normalization Rules

### 0) Programmatic Parsing Stack (LLM 없이)

| 도구 | 적용 범위 | 비용 |
|------|---------|------|
| `regex + section split` | Skills / Education / Experience 섹션 분리 | 무료 |
| `spaCy + NER` | 회사명/날짜/이름 엔티티 보강 (`en_core_web_sm` 계열) | 무료 |
| `dateparser` | 다양한 날짜 표기 정규화 | 무료 |
| `pdfplumber` + `pdfminer.six` | PDF 텍스트 추출 유틸 | 무료 |

> `src/backend/services/resume_parsing.py`에 통합되어 있고, ingestion에서는 `--parser-mode`로 제어.  
> `hybrid` 모드는 rule-based 결과가 충분하면 spaCy 호출을 생략하는 **조건부 보강** 전략을 사용.

**파서 준비(권장):**

```bash
# spaCy NER 모델
python -m spacy download en_core_web_sm

```

> 모델이 없으면 해당 파서는 자동 fallback되어 ingestion 자체는 계속 진행된다.

### 1) 공통 텍스트 클리닝 (`_clean_text`)

| 입력 | 변환 결과 |
|------|---------|
| `None`, `NaN`, `""` | `None` |
| `"nan"` / `"none"` / `"null"` / `"na"` / `"n/a"` (대소문자 무관) | `None` |
| 연속 공백 | 단일 공백으로 압축 |

### 2) Candidate ID 정규화 (`_normalize_identifier`)

| 데이터셋 | 원본 필드 | 변환 규칙 | 예시 |
|---------|---------|---------|------|
| Sneha | `ID` | `"sneha-{ID}"` | `16852973` → `sneha-16852973` |
| Suri | `person_id` | `"suri-{person_id}"` | `408` → `suri-408` |

> 목적: 데이터셋 간 ID 충돌 방지, source prefix로 식별성 강화

### 3) 스킬 정규화 (`_normalize_skill_list`)

| 처리 단계 | 내용 |
|---------|------|
| 공백 정리 | 앞뒤 공백 및 연속 공백 제거 |
| 소문자 변환 | 동의어 매핑 시 대소문자 무시 |
| 중복 제거 | 순서 보존 deduplication |
| `parsed.skills` | 원문 기반 정리 목록 |
| `parsed.normalized_skills` | 소문자 + 동의어 정규화 목록 |

**현재 동의어 맵 (`SKILL_NORMALIZATION_MAP`):**

| 입력 | 정규화 결과 |
|------|-----------|
| `ms excel`, `microsoft excel` | `excel` |
| `ms office` | `microsoft office` |
| `mongo db`, `mongo db-3.2` | `mongodb` |
| `ssrs` | `sql server reporting services` |

### 4) 날짜 정규화 (`_normalize_month`)

| 지원 입력 형식 | 저장 형식 |
|-------------|---------|
| `MM/YYYY` | `YYYY-MM` |
| `YYYY/MM` | `YYYY-MM` (`/00`이면 `YYYY-01` 보정) |
| `YYYY-MM` | `YYYY-MM` |
| `Mon YYYY` (예: `Jan 2020`) | `YYYY-MM` |
| `Month YYYY` (예: `January 2020`) | `YYYY-MM` |
| `Season YYYY` (예: `Fall 2014`) | `YYYY-MM` (`Fall/Autumn=09`, `Spring=03`, `Summer=06`, `Winter=12`) |
| `YYYY` (연도만) | `YYYY-01` |
| `"Present"` / `"Current"` / `"Now"` | `"present"` |

추가 규칙:
- 전처리로 접두어 제거: `from/since/starting/start/beginning/as of/effective ...`
- `08/YY`, `00/00`, `unknown`, `n/a` 등 불완전 값은 `None` 처리
- `dateparser` + 규칙 파서 조합 후에도 실패하면 원문 유지 대신 `None`으로 수렴
- 포맷이 제각각인 이력서 날짜(`from 2003`, `Fall 2014`, `2014/00`)를 `YYYY-MM`으로 통일

### 5) 경력 연수 / Seniority 파생

| 필드 | 계산 방법 |
|------|---------|
| `parsed.experience_years` | `experience_items[].start_date ~ end_date` 월수 합산 → `/ 12` (소수 1자리) |
| `parsed.seniority_level` | `< 2년` → `junior` / `< 5년` → `mid` / `< 8년` → `senior` / `≥ 8년` → `lead` |

### 6) Embedding Text 구성 (`_build_embedding_text`)

| 구성 요소 | 순서 | 제한 |
|---------|------|------|
| `Name: {name}` | 1 | Suri만 |
| `Category: {category}` | 2 | Sneha만 |
| `Summary: {summary}` | 3 | |
| `Skills: {normalized_skills[:30]}` | 4 | 최대 30개 |
| `Abilities: {abilities[:30]}` | 5 | Suri만 |
| `Experience titles: {titles[:20]}` | 6 | 중복 제거 |
| 최종 | — | 최대 4,000자 truncate |

### 7) 증분 처리 해시 (`normalization_hash`, `embedding_hash`)

| 필드 | 의미 |
|------|------|
| `ingestion.normalization_hash` | 정규화 결과 스냅샷 해시 (동일 문서 여부 판단) |
| `ingestion.embedding_hash` | 마지막 임베딩 동기화 해시 |
| `ingestion.embedding_upserted_at` | 마지막 Milvus 반영 시각 |

기본 동작:
- `normalization_hash`가 기존과 같으면 Mongo upsert 생략
- `embedding_hash == normalization_hash`면 재임베딩 생략
- 강제 재처리는 `--force-mongo-upsert`, `--force-reembed`로 수행

---

## Source-to-Target 필드 매핑

### Sneha (`Resume.csv`)

| 원본 필드 | Candidate 타깃 필드 | 비고 |
|---------|-----------------|------|
| `ID` | `candidate_id`, `source_keys.ID` | prefix `sneha-` |
| `Resume_str` | `raw.resume_text`, `parsed.summary` (앞 280자) | embedding fallback |
| `Resume_html` | `raw.resume_html` | |
| `Category` | `category` | |
| `Resume_str` | `metadata.name/email/phone` | regex + spaCy |
| `Resume_str` | `parsed.skills`, `parsed.normalized_skills` | regex + spaCy 보강 |
| `Resume_str` | `parsed.education[]`, `parsed.experience_items[]` | 섹션 기반 파싱 + spaCy 보강 |
| (파생) | `parsed.experience_years`, `parsed.seniority_level` | `experience_items` 기반 계산 |

### Suri (Structured CSV)

| 원본 파일·필드 | Candidate 타깃 필드 | 비고 |
|-------------|-----------------|------|
| `01_people.name` | `metadata.name` | |
| `01_people.email/phone/linkedin` | `metadata.email/phone/linkedin` | |
| `02_abilities.ability` | `parsed.abilities` | |
| `05_person_skills.skill` | `parsed.skills`, `parsed.normalized_skills` | |
| `03_education.program` | `parsed.education[].degree` | |
| `03_education.institution` | `parsed.education[].institution` | |
| `03_education.start_date` | `parsed.education[].start_date` | `_normalize_month` 적용 |
| `03_education.location` | `parsed.education[].location` | |
| `04_experience.title` | `parsed.experience_items[].title` | |
| `04_experience.firm` | `parsed.experience_items[].company` | |
| `04_experience.start_date/end_date` | `parsed.experience_items[].start_date/end_date` | `_normalize_month` 적용 |
| `04_experience.location` | `parsed.experience_items[].location` | |
| (파생) | `parsed.experience_years`, `parsed.seniority_level` | `_estimate_experience_years` |
| (파생, 첫 유효 location) | `metadata.location` | |
| — | `category` | **Suri는 None** (카테고리 없음) |

---

## 인프라 분리 적재 (Mongo / Milvus Split)

| 옵션 | 명령 | 설명 |
|------|------|------|
| Mongo만 | `--target mongo` | CSV → parse → MongoDB |
| Milvus만 (Mongo 기반) | `--target milvus --milvus-from-mongo` | MongoDB → embed → Milvus |
| 동시 적재 | `--target all` | CSV → parse → MongoDB + Milvus |
| 파서 모드 | `--parser-mode rule|spacy|hybrid` | Sneha 파싱 방식 선택 (`hybrid`: 규칙 파싱 후 부족할 때만 보강) |
| CSV 스트리밍 크기 | `--csv-chunk-size` | 대용량 CSV를 chunk 단위로 읽어 메모리 사용 절감 |
| 강제 Mongo 재적재 | `--force-mongo-upsert` | hash가 같아도 Mongo upsert 수행 |
| 강제 재임베딩 | `--force-reembed` | hash가 같아도 임베딩 재생성 |
| 점검 모드 | `--dry-run` | 실제 DB/벡터 반영 없이 배치 계획만 확인 |

---

## 성능 설계

| 항목 | 전략 |
|------|------|
| CSV 로딩 | `read_csv(chunksize=...)` 기반 streaming 처리 |
| Suri 보조 CSV 조인 | `person_id` 정렬 특성을 이용해 목표 ID 범위 초과 시 스캔 조기 종료 |
| Parser 성능 | spaCy 로더는 1회 초기화 후 재사용 (row당 재로딩 방지) |
| Hybrid 최적화 | rule-based 결과가 충분하면 spaCy 호출 생략 (조건부 보강) |
| 파서 실패 내성 | spaCy 런타임 실패 시 해당 프로세스에서 자동 비활성화 후 진행 |
| OpenAI 임베딩 | 배치 호출 (`embed_texts`, `batch_size=32`) |
| MongoDB upsert | `bulk_write` (ordered=False) |
| Milvus upsert | 동일 `(source_dataset, candidate_id)` 삭제 후 insert |
| Milvus 안정성 | delete 전 `collection.load()` 보장 (일부 배포 환경에서 `collection not loaded` 방지) |
| 재실행 비용 절감 | hash 기반 증분 처리로 unchanged 문서 skip |

---

## 권장 실행 순서

```bash
# Step 1: MongoDB 적재
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target mongo --parser-mode hybrid \
  --sneha-limit 200 --suri-limit 500

# Step 2: Milvus 적재
PYTHONPATH=src python src/backend/services/ingest_resumes.py \
  --source all --target milvus --milvus-from-mongo \
  --sneha-limit 200 --suri-limit 500
```

---

## 운영 스냅샷 (2026-03-13)

| 항목 | 결과 |
|------|------|
| Mongo 재적재 | `Sneha 2484 + Suri 3000 = 5484` upsert 완료 |
| 날짜 정규화 품질 | `invalid_dates_edu = 0`, `invalid_dates_exp = 0` (두 데이터셋 모두) |
| Milvus 증분 임베딩 | `seen=5484`, `embedded=5484`, `embed_skipped=0` |
| Mongo 임베딩 동기화 | `embedding_hash null = 0`, `embedding_upserted_at null = 0`, `normalization_hash == embedding_hash` 불일치 `0` |

> 참고: Milvus `num_entities`가 Mongo 문서 수보다 클 수 있다(과거 잔여 벡터).  
> 현재 증분 업서트는 입력 대상 `(source_dataset, candidate_id)`만 갱신하며, 전체 orphan purge는 별도 작업으로 수행한다.

---

## ⚠️ Normalization Gap 분석 — Agentic AI 연계 관점

> **핵심 결정 (ADR-003)**: Ingestion 파싱은 생성형 LLM 사용 ❌. Null 필드는 RAG pipeline에서 raw_text 컨텍스트로 처리.

### GAP 요약표

| Gap ID | 대상 | 부족한 필드 | 영향 Agent | 심각도 | 대응 전략 |
|--------|------|-----------|-----------|-------|---------|
| **G-01** | Sneha 일부 | `experience_years = None`, `seniority_level = None` | ExperienceEvalAgent | 🟡 중간 | parser-mode=`hybrid` 유지 + null 시 `raw.resume_text` fallback |
| **G-02** | Sneha 일부 | `parsed.experience_items = []` | ExperienceEvalAgent, TechnicalEvalAgent | 🟡 중간 | regex/global date range + spaCy 보강 후 fallback |
| **G-03** | Sneha 일부 | `parsed.education = []` | ExperienceEvalAgent | 🟡 중간 | degree 패턴 확장 + null 시 scoring weight 조정 |
| **G-04** | Suri | `category = None` | SkillMatchingAgent 필터, CultureFitAgent | 🟡 중간 | Abilities/Skills로 대체 판단. Milvus 필터 미적용 |
| **G-05** | Sneha 일부 | `parsed.skills` 빈 리스트 (regex 실패) | SkillMatchingAgent | 🟡 중간 | spaCy 보강 + `raw.resume_text` fallback |
| **G-06** | 양쪽 | `SKILL_NORMALIZATION_MAP` 규칙 수 제한 | SkillMatchingAgent | 🟡 중간 | 동의어 맵 점진적 확장 (LLM 없이) |
| **G-07** | Suri | `experience_items[].description = None` | TechnicalEvalAgent, CultureFitAgent | 🟡 중간 | Abilities 텍스트를 컨텍스트에 포함 |
| **G-08** | Suri | `summary`가 `"{name} resume profile"` 수준 | 전반 | 🟢 낮음 | Abilities + Skills로 embedding_text 보강 (이미 구현) |
| **G-09** | 양쪽 | embedding_text 구성 방식 상이 | Retriever/Ranking | 🟡 중간 | 공통 템플릿 유지 + 필드 가중치 튜닝으로 편향 완화 |

### 보완 전략 (모두 LLM 없이)

```
Ingestion (오프라인, 1회, LLM ❌)
  현재 (v3): regex + spaCy + dateparser (hybrid, 조건부 보강)
  fallback: parser-mode=rule 로 강등 가능
  재실행 시: hash 비교로 변경분만 Mongo/Milvus 반영

RAG Pipeline (매칭 요청 시)
  정상 경로: MongoDB 구조화 필드(skills/experience_items 등) 사용
  Fallback: null 필드 있을 경우 raw.resume_text를 CandidateContext에 포함
            → Agent가 JD와 함께 필요한 범위만 직접 판단
```

### Agent별 Null 필드 처리 방식

| Agent | null 상황 | RAG Pipeline 처리 |
|-------|---------|-----------------|
| `SkillMatchingAgent` | Sneha skills 빈 리스트 | `raw.resume_text` 컨텍스트 포함 → Agent가 JD 기반 스킬 판단 |
| `ExperienceEvalAgent` | Sneha `experience_years=None`, 경력 없음 | `raw.resume_text` 포함 → Agent가 텍스트에서 경력 추정 |
| `TechnicalEvalAgent` | Sneha 경력 description 없음 | `raw.resume_text` 포함 → 기술 스택 텍스트 참조 |
| `CultureFitAgent` | Suri `category=None` | Abilities 텍스트 컨텍스트 포함 → domain fit 판단 |
| `RankingAgent` | score 일부 불완전 | 가용 점수만으로 가중 합산, 불완전 필드 explanation에 명시 |

> `ResumeParsingAgent`는 **운용하지 않음** (ADR-003). 파싱은 ingestion rule-based로 완결, 부족한 부분은 RAG context로 보완.
