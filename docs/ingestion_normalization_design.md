# Ingestion Normalization Design (V2)

Date: 2026-03-13

## 왜 스키마를 변경했는가

- 기존 `parsed.normalized_skills` 단일 축만으로는 scoring 설명력과 ontology 추적성이 부족했다.
- 역할/버전/업무 capability 문구를 core skill과 분리해야 hybrid scoring이 안정화된다.
- 버전 메타가 없으면 Mongo/Milvus 재생성 시 어떤 기준으로 적재되었는지 추적하기 어렵다.

## 새 parsed skill 구조

`ParsedSection`에 아래 필드를 확장했다.

- `skills`: 원본 추출 skill
- `normalized_skills`: lexical normalization 결과
- `canonical_skills`: alias 적용 canonical
- `core_skills`: scoring 핵심 skill
- `expanded_skills`: taxonomy parent 확장 결과
- `capability_phrases`: 업무 행위/운영 문구
- `role_candidates`: 역할/직무 문구
- `review_required_skills`: 자동 판단 보류 문구
- `versioned_skills`: `{raw, canonical, version}`

## 버전 관리 방식

`ingestion` 메타에 다음을 저장한다.

- `parsing_version`
- `normalization_version`
- `taxonomy_version`
- `embedding_text_version`
- `experience_years_method`
- `alias_applied`
- `taxonomy_applied`

또한

- `normalization_hash`: v2 canonical payload 기준
- `embedding_hash`: `embedding_text + embedding_text_version + normalization_hash` 기준

## Experience Years 계산 방식

- 기존 단순 합산을 제거하고 `month-union` 방식으로 변경했다.
- 겹치는 경력 구간은 중복 합산하지 않는다.
- 메타에 `experience_years_method=month-union-v1`를 기록한다.

## 최종 운영 ontology 파일

런타임 ingestion은 아래 파일만 읽는다.

- `config/skill_aliases.yml`
- `config/skill_taxonomy.yml`
- `config/skill_role_candidates.yml`
- `config/versioned_skills.yml`
- `config/skill_capability_phrases.yml`
- `config/skill_review_required.yml`

분석/정제 이력은 `docs/ontology/`에 보관한다.

## 왜 clean rebuild가 필요한가

- 정규화 payload와 hash 기준이 변경되었고,
- embedding text 구성 및 `embedding_hash` 기준도 변경되었기 때문이다.
- 기존 Mongo/Milvus 데이터는 새 contract와 hash 기준과 불일치할 수 있어 재생성이 안전하다.

## 권장 재적재 순서

1. `candidates` 컬렉션 드롭
2. ingestion 재실행 (`--target all --force-mongo-upsert --force-reembed`)
3. API 조회/매칭 smoke test
