# NotebookLM 분석 가이드 및 프롬프트

현재 이력서 매칭 백엔드의 처리 흐름은 최신 AI 에이전트 기술(Multi-Agent)과 기존 정보 검색(RAG)이 결합된 하이브리드 구조입니다. 시스템이 어떻게 동작하고, 예외 상황에서 어떻게 안전하게 결과를 내보내는지(Fallback) NotebookLM을 통해 깊이 분석할 수 있도록 가이드를 제공합니다.

## 1. NotebookLM에 업로드할 핵심 소스 파일 목록

NotebookLM에서 전체 흐름을 완벽히 이해하려면 아래 핵심 파일 5~6개 정도만 업로드하시는 것이 가장 효율적입니다. 코드가 길어지면 토큰을 많이 소모하므로 가장 뼈대가 되는 파일들을 추려드립니다.

업로드 파일 목록 (경로: `src/backend/...` 내 위치):
1. **`services/matching_service.py`**: 파이프라인의 시작점. (JDBC 검색 ➔ 필터링 ➔ 랭킹 ➔ 최종 에이전트 채점 및 Fairness(공정성) 검사). 방금 도입한 **병렬 처리(ThreadPoolExecutor)**가 있는 곳입니다.
2. **`agents/runtime/service.py`**: 전체 에이전트 오케스트레이션을 담당. 최신 SDK(1번) -> 기존 단일 프롬프트(2번) -> 휴리스틱(3번) 순서로 **Fallback 안전망**을 관장합니다.
3. **`agents/runtime/sdk_runner.py`**: 실제 SDK의 6개 에이전트(Skill, Experience, Technical, Culture 평가자 4명 + Recruiter, Hiring Manager 통역/협상가 2명)가 정의된 핵심 파일입니다. RAG가 여기서 **도구(Tool)**로 주입됩니다.
4. **`repositories/hybrid_retriever.py`**: 키워드 검색, 벡터 검색을 혼합한 **RAG (Hybrid Search)** 로직입니다. 특히, `search_within_candidate` 메서드가 에이전트들이 사용하는 "돋보기(Tool)" 역할입니다.
5. (선택적) **`schemas/job.py`**, **`agents/contracts/skill_agent.py`** 등: 구조체(Model)가 궁금하다면 `contracts/` 안의 Pydantic 폼들을 보면 좋습니다.

---

## 2. NotebookLM 전용 마스터 프롬프트

이 프롬프트를 복사해서 NotebookLM의 채팅창에 **첫 질문**으로 던지세요.

```markdown
당신은 최고 수준의 AI/소프트웨어 아키텍트입니다.
업로드된 소스코드를 바탕으로, "Resume Matching Project"의 **핵심 파이프라인 처리 흐름**을 상세하면서도 매우 알기 쉽게 분석해 주세요. 특히 다음 사항들에 초점을 맞추어 설명해 주십시오.

### 분석 요청 사항:
1. **전체 파이프라인 구성 요약**: 사용자의 텍스트(JD)가 입력되어 최종적으로 Top K 후보자가 나오기까지의 전체 여정(Retrieval -> Enrichment -> Shortlisting -> Scoring(Agent) -> Fairness)을 다이어그램(Mermaid) 또는 순서도로 그려주세요.
2. **에이전트 채점 시스템 (Agent Orchestration)**: 
   - `AgentOrchestrationService`가 어떻게 3단계 안전망(Fallback 아키텍처)을 구성하고 작동하는지 설명해주세요. (Agents SDK -> Live Runner -> Heuristic)
   - 평가용 하위 에이전트 4명(Skill, Experience, Technical, Culture)과 협상용 2명(Recruiter, Hiring Manager)이 서로 어떤 데이터를 주고받으며 최종 점수(Handoff / Negotiation)를 픽셀화하는지 알려주세요.
3. **RAG-as-a-Tool 시너지**: 
   - 에이전트들이 모르는 정보나 증거가 부족할 때, 어떻게 스스로 `search_candidate_evidence` 도구를 활용하여 이력서 원문을 뒤지는지(RAG) 코드 레벨에서 그 연결성을 설명해 주세요.
4. **성능 병목(Latency) 및 동시성 처리**: 
   - 이 시스템이 다수(Top K)의 지원자를 채점할 때 시간이 오래 걸리는 구조적 한계를 어떻게 돌파했는지, `matching_service.py` 내의 `ThreadPoolExecutor` 적용 부분을 짚어서 설명해 주세요.

마지막으로, 코딩이나 AI 지식이 깊지 않은 현업 기획자가 읽어도 완벽히 이해가 가도록 비유를 섞어(예: 4명의 면접관과 2명의 채용담당자 등) 흥미롭게 요약해 주세요.
```

## 3. 작동 원리 (매우 간략한 비유)

위 파이프라인이 너무 복잡해 보일 수 있으니, 현실의 채용 면접에 비유해 드릴게요!

1. **서류 전형 (Retrieval & Shortlist)**: 이력서 더미에서 JD(직무)와 잘 맞는 Top 후보자 K명을 빠르게 골라냅니다. (`matching_service.py`)
2. **실무진 면접 (Agent SDK Evaluators)**: 4명의 깐깐한 실무 면접관(Skill, Experience, Technical, Culture)이 각자의 분야만 집중적으로 분석합니다. 만약 이력서에서 `Kubernetes`라는 단어를 못 찾으면, 그냥 "0점"을 주지 않고 `search_candidate_evidence`라는 **돋보기(RAG 검색 도구)**를 써서 이력서 구석구석을 다시 뒤져봅니다. (`sdk_runner.py`)
3. **임원진 합의 (Negotiation / Handoff)**: 실무진들의 평가 결과를 바탕으로, 인사팀장(Recruiter)과 현업 팀장(Hiring Manager)이 각 항목별 가중치를 협상하여(Handoff) **최종 등수(Score)**를 결정합니다. (`sdk_runner.py`)
4. **인재개발팀 감사 (Fairness)**: 혹시라도 면접관들이 성별, 학벌 등 편향된 평가를 했는지 스캔하고, 지원자들을 최종 정렬합니다. (`matching_service.py`)
5. **플랜 B (Fallback 구조)**: 만약 1명의 실무 면접관(SDK)이 갑자기 아프거나(에러/타임아웃 발생) 연락이 안 되면 당황하지 않고, 혼자서 4명 몫을 뛰는 만능 대타(Live Runner)가 투입되어 무조건 면접은 마무리를 짓습니다. (`service.py`)

NotebookLM에 파일들을 업로드하시고 프롬프트를 넣으시면, 코드를 줄줄 외울 정도로 명확하게 전체 시스템을 가이드해 줄 것입니다. 해보시고 막히는 점 있으면 바로 알려주세요!
