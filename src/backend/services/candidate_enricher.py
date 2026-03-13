from __future__ import annotations

from typing import Any

from backend.repositories.mongo_repo import get_candidates_by_ids


def enrich_hits(hits: list[dict[str, Any]], *, min_experience_years: float | None) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    if not hits:
        return []

    candidate_ids = [hit["candidate_id"] for hit in hits if hit.get("candidate_id")]
    docs_by_id = get_candidates_by_ids(candidate_ids)

    enriched: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for hit in hits:
        if min_experience_years is not None:
            exp = hit.get("experience_years")
            if exp is None or exp < min_experience_years:
                continue

        candidate_id = hit.get("candidate_id")
        if not candidate_id:
            continue
        candidate_doc = docs_by_id.get(candidate_id)
        if not candidate_doc:
            continue
        enriched.append((hit, candidate_doc))

    return enriched
