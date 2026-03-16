from __future__ import annotations

import concurrent.futures
import logging
from dataclasses import dataclass
from typing import Any, Callable, Iterable, TypeVar

from backend.schemas.job import JobMatchCandidate

T = TypeVar("T")


@dataclass(frozen=True)
class CandidateTask:
    idx: int
    hit: dict[str, Any]
    candidate_doc: dict[str, Any]


def select_agent_eval_indices(
    prelim_results: list[JobMatchCandidate],
    agent_eval_top_n: int,
) -> tuple[list[int], set[int]]:
    sorted_indices = sorted(
        range(len(prelim_results)),
        key=lambda idx: prelim_results[idx].score,
        reverse=True,
    )
    selected_indices = sorted_indices[: max(0, int(agent_eval_top_n))]
    return selected_indices, set(selected_indices)


def run_candidate_tasks_with_isolation(
    *,
    tasks: Iterable[CandidateTask],
    evaluate_task: Callable[[CandidateTask], T],
    on_task_error: Callable[[CandidateTask, Exception], T] | None,
    logger: logging.Logger,
    max_workers: int = 10,
) -> list[T]:
    task_list = list(tasks)
    if not task_list:
        return []

    results: list[T] = []
    pool_size = max(1, min(max_workers, len(task_list)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=pool_size) as executor:
        future_to_task = {
            executor.submit(evaluate_task, task): task
            for task in task_list
        }
        for future in concurrent.futures.as_completed(future_to_task):
            task = future_to_task[future]
            try:
                results.append(future.result())
            except Exception as exc:
                if on_task_error is None:
                    raise
                logger.exception(
                    "candidate_eval_failed idx=%s candidate_id=%s; applying deterministic fallback.",
                    task.idx,
                    task.hit.get("candidate_id"),
                )
                results.append(on_task_error(task, exc))
    return results


def run_scoped_candidate_evaluation(
    *,
    shortlisted_hits: list[tuple[dict[str, Any], dict[str, Any]]],
    eval_index_set: set[int],
    evaluate_with_agent: Callable[[dict[str, Any], dict[str, Any]], T],
    build_deterministic: Callable[[dict[str, Any], dict[str, Any], str], T],
    outside_scope_reason: str,
    logger: logging.Logger,
    max_workers: int = 10,
) -> list[T]:
    def _evaluate_task(task: CandidateTask) -> T:
        if task.idx in eval_index_set:
            return evaluate_with_agent(task.hit, task.candidate_doc)
        return build_deterministic(task.hit, task.candidate_doc, outside_scope_reason)

    def _on_task_error(task: CandidateTask, exc: Exception) -> T:
        return build_deterministic(
            task.hit,
            task.candidate_doc,
            f"agent_evaluation_failed({exc.__class__.__name__})",
        )

    tasks = [
        CandidateTask(idx=idx, hit=hit, candidate_doc=candidate_doc)
        for idx, (hit, candidate_doc) in enumerate(shortlisted_hits)
    ]
    return run_candidate_tasks_with_isolation(
        tasks=tasks,
        evaluate_task=_evaluate_task,
        on_task_error=_on_task_error,
        logger=logger,
        max_workers=max_workers,
    )
