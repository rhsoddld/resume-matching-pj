from typing import Optional

from backend.core.database import get_collection

def get_candidate_by_id(candidate_id: str) -> Optional[dict]:
    """Retrieve a single candidate document by its candidate_id."""
    candidates = get_collection("candidates")
    doc = candidates.find_one({"candidate_id": candidate_id})
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc
