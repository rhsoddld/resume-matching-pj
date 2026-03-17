# 📋 Reviewer Checklist: The "Senior+" Production Standard

[cite_start]이 체크리스트는 단순한 기능을 구현한 코드를 넘어, 실제 운영 환경(Production-Ready)에 적합한 시스템인지를 검증하기 위한 상세 가이드입니다. [cite: 1, 104, 105]

**요구사항 매핑·증거 위치:** 각 체크 항목과 Problem Definition / Functional Requirements / 구현 증거의 매핑은 [docs/governance/TRACEABILITY.md](../docs/governance/TRACEABILITY.md)에서 확인할 수 있습니다.

---

## 1. Filesystem & Documentation (파일 시스템 및 문서화)
* [cite_start]**명확한 폴더 구조:** 프로젝트가 도메인 및 서비스별로 논리적으로 구조화되어 있는가? [cite: 4, 5, 144, 145]
    * [cite_start]`/requirements`: 원본 프로젝트 요구사항 및 사양서 [cite: 6]
    * [cite_start]`/docs/architecture`: 고수준 시스템 디자인 다이어그램 [cite: 7]
    * [cite_start]`/docs/data-flow`: 데이터 수집(Ingestion), 검색(Retrieval) 등 구체적인 로직 흐름 [cite: 8]
    * [cite_start]`/src`: 운영 구현 코드 (서비스/도메인별 구조화) [cite: 9]
    * [cite_start]`/tests`: API 및 성능 테스트 슈트 [cite: 10]
* [cite_start]**README.md:** 명확한 설치 및 평가 가이드를 제공하며, 실제 코드와 구조가 일치하는가? [cite: 11, 13]
* [cite_start]**Stakeholder PPT:** EDA, 디자인 결정, 평가 결과가 포함된 요약 브리핑 덱이 있는가? [cite: 12]

## 2. Architecture & Design Integrity (아키텍처 및 디자인 무결성)
* [cite_start]**Architecture vs Data Flow:** 소프트웨어 컴포넌트(Architecture)와 논리적 데이터 이동(Data Flow)을 혼동하지 않고 명확히 구분했는가? [cite: 15, 16, 17]
* [cite_start]**운영 규모 배포 (Production Scale):** 아키텍처가 API Gateway, Load Balancer, Kubernetes(K8s)를 고려하고 있는가? [cite: 18, 19]
* [cite_start]**POC vs Production:** POC와 실제 운영 환경에서 적용되는 범위의 차이를 명확히 정의했는가? [cite: 20]
* [cite_start]**관측성 및 MLOps:** 모니터링, 로깅, ML 라이프사이클 레이어가 아키텍처에 명시적으로 포함되었는가? [cite: 21, 102]
* [cite_start]**디자인 결정 (ADR):** 주요 선택에 대한 장단점과 근거(예: DECISIONS.md)를 통해 '왜(Why)'를 설명했는가? [cite: 22, 23, 142, 143]
* [cite_start]**결합도 분리 (Decoupling):** 코어 API 수정 없이 Vector DB 등을 교체할 수 있는 구조인가? [cite: 25, 112]

## 3. Implementation & Code Quality (구현 및 코드 품질)
* [cite_start]**Zero print():** `print()` 문을 완전히 제거하고 100% 구조화된 로깅(JSON 등)을 사용했는가? [cite: 27, 138]
* [cite_start]**보안 및 클린 코드:** 하드코딩된 Secret이 없으며, 비대한 단일 "God" 파일 없이 모듈화되었는가? [cite: 35, 124]
* [cite_start]**커넥션 풀링:** DB 및 외부 서비스 호출 시 TCP 오버헤드를 줄이기 위해 항상 사용되는가? [cite: 37, 119]
* [cite_start]**입출력 검증:** Pydantic 등을 사용하여 API 스키마 유효성을 엄격하게 검사하는가? [cite: 38, 126]
* [cite_start]**컨테이너화:** `Dockerfile` 및 `docker-compose.yml`을 통해 "원 커맨드" 실행이 가능한가? [cite: 39, 136]
* [cite_start]**리소스 관리:** 대용량 데이터 처리 시 Generator/Streaming을 사용하여 메모리를 효율적으로 쓰는가? [cite: 44, 120]
* [cite_start]**Cold Start 최적화:** 모델이나 인덱스를 첫 요청 시점이 아닌 시스템 시작 시 미리 로드하는가? [cite: 45, 133, 134]

## 4. Testing & Validation (테스트 및 유효성 검증)
* [cite_start]**자동화된 테스트:** 데이터 로딩(수집) 및 검색(Retrieval) 전 과정에 대한 API 테스트가 있는가? [cite: 49, 99]
* [cite_start]**성능 측정:** Latency(p99)와 Throughput(처리량)을 모니터링하고 기록하는가? [cite: 50]
* [cite_start]**정확도 평가 (Evaluation):** LLM-as-Judge나 IR Metrics(NDCG, MAP) 등 정량적 평가 방법론이 있는가? [cite: 51, 128, 130]
* [cite_start]**Ground Truth:** 자체 평가를 위해 사용된 데이터셋이 문서화되어 제공되는가? [cite: 52, 132]
* [cite_start]**복구 탄력성 (Resiliency):** 외부 API 장애 시 로컬 모델(Flan-T5 등)로 전환되는 Fallback 로직이 있는가? [cite: 63, 64, 116]

---

## [cite_start]5. Reviewer's Verdict (SME 'Yes' Grade 기준) [cite: 67, 147, 148]

| 항목 | "Yes" 판정 기준 (Senior+ Standard) |
| :--- | :--- |
| **정확성** | 견고하며, 에지 케이스(Empty data, API 타임아웃 등)를 처리함 |
| **아키텍처** | 모듈형 마이크로서비스. DB, AI, API 레이어의 명확한 분리 |
| **디자인 결정** | ADR 포함. 비용, 지연 시간, 복잡성에 따른 기술 선택의 정당화 |
| **성능** | 파이프라인 최적화. 병렬 수집, 가벼운 SLM 활용, 분산 캐싱 |
| **확장성** | Cloud-Ready. Stateless 구조, 수평 확장 가능, 커넥션 풀링 |
| **신뢰성** | 재시도 로직, 로컬 Fallback, 서킷 브레이커 구현 |
| **유지보수성** | 자기설명적 코드(Self-Documenting), 논리적 그룹화, Docker 기반 |
| **관측성** | 구조화된 로그 및 기능적인 헬스 체크 엔드포인트 완비 |

---