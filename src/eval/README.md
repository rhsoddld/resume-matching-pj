# Eval README

이 디렉토리는 골든셋 관리, 짧은 평가 루프, judge annotation, 리포트 생성을 위한 최소 파일만 남긴 영역입니다.

## Start Here

- 실행 진입점: [eval_runner.py](/Users/lee/Desktop/resume-matching-pj/src/eval/eval_runner.py)
- 현재 결론 요약: [RESULTS.md](/Users/lee/Desktop/resume-matching-pj/src/eval/RESULTS.md)
- subset 생성: [create_mode_subsets.py](/Users/lee/Desktop/resume-matching-pj/src/eval/create_mode_subsets.py)
- LLM judge annotation 생성: [generate_llm_judge_annotations.py](/Users/lee/Desktop/resume-matching-pj/src/eval/generate_llm_judge_annotations.py)

## Core Files

- [config.py](/Users/lee/Desktop/resume-matching-pj/src/eval/config.py)
  - eval 모드별 설정
- [metrics.py](/Users/lee/Desktop/resume-matching-pj/src/eval/metrics.py)
  - retrieval/rerank/agent 평가 함수
- [reporting.py](/Users/lee/Desktop/resume-matching-pj/src/eval/reporting.py)
  - markdown/json 리포트 생성
- [golden_set.jsonl](/Users/lee/Desktop/resume-matching-pj/src/eval/golden_set.jsonl)
  - 원본 골든셋
- [golden_set.normalized.jsonl](/Users/lee/Desktop/resume-matching-pj/src/eval/golden_set.normalized.jsonl)
  - 정규화 버전
- [llm_judge_annotations.jsonl](/Users/lee/Desktop/resume-matching-pj/src/eval/llm_judge_annotations.jsonl)
  - 현재 judge annotation 결과

## Subsets

- subset 설명: [subsets/README.md](/Users/lee/Desktop/resume-matching-pj/src/eval/subsets/README.md)
- active agent subset: [golden.agent.jsonl](/Users/lee/Desktop/resume-matching-pj/src/eval/subsets/golden.agent.jsonl)
- active hybrid subset: [golden.hybrid.jsonl](/Users/lee/Desktop/resume-matching-pj/src/eval/subsets/golden.hybrid.jsonl)
- active rerank subset: [golden.rerank.jsonl](/Users/lee/Desktop/resume-matching-pj/src/eval/subsets/golden.rerank.jsonl)

## Outputs

- kept reviewer summary root: `src/eval/outputs/short_eval/manual/`
- current judged agent run:
  - [final_eval_report.md](/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4_judged/final_eval_report.md)
  - [agent_eval.json](/Users/lee/Desktop/resume-matching-pj/src/eval/outputs/short_eval/manual/agent6_livejson_top4_v4_judged/agent_eval.json)

## Current Rule Of Thumb

- retrieval: hybrid 유지
- rerank: 기본 비활성
- agent eval: eval에서는 `sdk_handoff` 사용 안 함
- current tuning point: `agent_eval_top_n=4`
- judge: golden truth 대체가 아니라 보조 축
