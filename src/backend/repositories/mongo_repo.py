from typing import Optional

from backend.core.collections import dedupe_preserve
from backend.core.database import get_collection
from backend.core.exceptions import RepositoryError


def _normalize_doc(doc: dict | None) -> dict | None:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc

def get_candidate_by_id(candidate_id: str) -> Optional[dict]:
    """Retrieve a single candidate document by its candidate_id."""
    candidates = get_collection("candidates")
    try:
        return _normalize_doc(candidates.find_one({"candidate_id": candidate_id}))
    except Exception as exc:
        raise RepositoryError("Failed to read candidate document.") from exc


def get_candidates_by_ids(candidate_ids: list[str]) -> dict[str, dict]:
    """Batch-load candidate documents indexed by candidate_id."""
    if not candidate_ids:
        return {}

    candidates = get_collection("candidates")
    unique_ids = [candidate_id for candidate_id in dedupe_preserve(candidate_ids) if candidate_id]
    try:
        cursor = candidates.find({"candidate_id": {"$in": unique_ids}})
        docs: dict[str, dict] = {}
        for doc in cursor:
            normalized = _normalize_doc(doc)
            if not normalized:
                continue
            candidate_id = normalized.get("candidate_id")
            if candidate_id:
                docs[candidate_id] = normalized
        return docs
    except Exception as exc:
        raise RepositoryError("Failed to batch-read candidate documents.") from exc
