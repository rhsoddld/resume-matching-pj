from pathlib import Path
import logging
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from backend.services.matching.evaluation import (  # noqa: E402
    CandidateTask,
    run_candidate_tasks_with_isolation,
    select_agent_eval_indices,
)


def test_run_candidate_tasks_with_isolation_uses_fallback_per_candidate():
    tasks = [
        CandidateTask(idx=0, hit={"candidate_id": "c0"}, candidate_doc={}),
        CandidateTask(idx=1, hit={"candidate_id": "c1"}, candidate_doc={}),
        CandidateTask(idx=2, hit={"candidate_id": "c2"}, candidate_doc={}),
    ]

    def _evaluate(task: CandidateTask) -> str:
        if task.idx == 1:
            raise RuntimeError("agent timeout")
        return f"ok-{task.idx}"

    def _fallback(task: CandidateTask, exc: Exception) -> str:
        return f"fallback-{task.idx}-{exc.__class__.__name__}"

    results = run_candidate_tasks_with_isolation(
        tasks=tasks,
        evaluate_task=_evaluate,
        on_task_error=_fallback,
        logger=logging.getLogger(__name__),
    )

    assert set(results) == {"ok-0", "ok-2", "fallback-1-RuntimeError"}


def test_run_candidate_tasks_with_isolation_raises_without_fallback():
    tasks = [CandidateTask(idx=0, hit={"candidate_id": "c0"}, candidate_doc={})]

    def _evaluate(task: CandidateTask) -> str:
        raise ValueError(f"bad-{task.idx}")

    with pytest.raises(ValueError):
        run_candidate_tasks_with_isolation(
            tasks=tasks,
            evaluate_task=_evaluate,
            on_task_error=None,
            logger=logging.getLogger(__name__),
        )


def test_select_agent_eval_indices_orders_by_score_desc():
    prelim_results = [
        SimpleNamespace(score=0.2, candidate_id="a"),
        SimpleNamespace(score=0.9, candidate_id="b"),
        SimpleNamespace(score=0.5, candidate_id="c"),
    ]
    selected_indices, selected_set = select_agent_eval_indices(prelim_results, 2)

    assert selected_indices == [1, 2]
    assert selected_set == {1, 2}
