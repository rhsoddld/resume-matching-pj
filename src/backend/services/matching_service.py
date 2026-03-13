import logging
from pathlib import Path
import re
from typing import List

from backend.core.vector_store import search_embeddings
from backend.repositories.mongo_repo import get_candidate_by_id
from backend.services.scoring_service import compute_deterministic_match_score, compute_skill_overlap
from backend.services.skill_ontology import RuntimeSkillOntology

logger = logging.getLogger(__name__)


ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "config"
_SKILL_SPLIT_RE = re.compile(r"[,\n;/|]+")
_SKILL_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+.#-]{1,}")
_YEARS_RE = re.compile(r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)", re.IGNORECASE)
_SKILL_STOPWORDS = {
    "and",
    "or",
    "the",
    "with",
    "for",
    "from",
    "into",
    "years",
    "year",
    "experience",
    "required",
    "preferred",
    "plus",
}
_SENIORITY_KEYWORDS = ("intern", "junior", "mid", "senior", "lead", "staff", "principal")

try:
    ONTOLOGY = RuntimeSkillOntology.load_from_config(CONFIG_DIR)
except Exception:
    ONTOLOGY = None
    logger.exception("Skill ontology load failed; fallback JD skill extraction will be used.")


def _dedupe_preserve(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def _extract_job_skill_candidates(job_description: str) -> list[str]:
    if not job_description:
        return []

    lowered = job_description.lower()
    chunks = [part.strip() for part in _SKILL_SPLIT_RE.split(lowered)]

    candidates: list[str] = []
    for chunk in chunks:
        if not chunk:
            continue
        cleaned = re.sub(r"\s+", " ", chunk).strip(" .:-")
        if cleaned and len(cleaned) <= 64:
            candidates.append(cleaned)
        for token in _SKILL_TOKEN_RE.findall(cleaned):
            if token in _SKILL_STOPWORDS:
                continue
            candidates.append(token)
    return _dedupe_preserve(candidates)


def _build_job_skill_profile(job_description: str) -> dict:
    raw_candidates = _extract_job_skill_candidates(job_description)
    if ONTOLOGY is None:
        return {
            "required_skills": raw_candidates,
            "expanded_skills": raw_candidates,
        }

    normalized = ONTOLOGY.normalize(raw_skills=raw_candidates, abilities=[])
    required_skills = normalized.core_skills or normalized.canonical_skills or normalized.normalized_skills
    expanded_skills = normalized.expanded_skills or required_skills
    return {
        "required_skills": _dedupe_preserve(required_skills),
        "expanded_skills": _dedupe_preserve(expanded_skills),
    }


def _extract_required_experience_years(job_description: str) -> float | None:
    if not job_description:
        return None
    matches = [float(value) for value in _YEARS_RE.findall(job_description)]
    if not matches:
        return None
    return max(matches)


def _extract_preferred_seniority(job_description: str) -> str | None:
    lowered = job_description.lower()
    for keyword in _SENIORITY_KEYWORDS:
        if keyword in lowered:
            return keyword
    return None


class MatchingService:
    def match_jobs(self, job_description: str, top_k: int = 10, category: str = None, min_experience_years: float = None) -> List[dict]:
        # Simple rule: use OpenAI to embed the job_description
        # We need to import the OpenAI client.
        from openai import OpenAI
        from backend.core.settings import settings
        
        client = OpenAI(api_key=settings.openai_api_key)
        response = client.embeddings.create(
            input=[job_description],
            model=settings.openai_embedding_model
        )
        query_vector = response.data[0].embedding
        job_skill_profile = _build_job_skill_profile(job_description)
        required_experience_years = _extract_required_experience_years(job_description)
        preferred_seniority = _extract_preferred_seniority(job_description)
        
        # Search Milvus
        hits = search_embeddings(query_vector=query_vector, top_k=top_k, category=category)
        
        results = []
        for hit in hits:
            # Experience filter natively in mongo or just local filter since milvus returned it
            if min_experience_years is not None:
                exp = hit.get("experience_years")
                if exp is None or exp < min_experience_years:
                    continue
            
            # Enrich with Mongo Data
            candidate_doc = get_candidate_by_id(hit["candidate_id"])
            if candidate_doc:
                parsed = candidate_doc.get("parsed", {})
                skill_overlap_score, skill_overlap_detail = compute_skill_overlap(candidate_doc, job_skill_profile)
                final_score, final_score_detail = compute_deterministic_match_score(
                    raw_similarity=float(hit["score"]),
                    skill_overlap=skill_overlap_score,
                    candidate_experience_years=hit.get("experience_years"),
                    required_experience_years=required_experience_years,
                    candidate_seniority=hit.get("seniority_level"),
                    preferred_seniority=preferred_seniority,
                    category_matched=bool(category and hit.get("category") == category),
                )
                results.append({
                    "candidate_id": hit["candidate_id"],
                    "category": hit.get("category"),
                    "summary": parsed.get("summary"),
                    "skills": parsed.get("skills", []),
                    "normalized_skills": parsed.get("normalized_skills", []),
                    "core_skills": parsed.get("core_skills", []),
                    "expanded_skills": parsed.get("expanded_skills", []),
                    "experience_years": hit.get("experience_years"),
                    "seniority_level": hit.get("seniority_level"),
                    "score": round(float(final_score), 4),
                    "vector_score": round(float(hit["score"]), 4),
                    "skill_overlap": round(float(skill_overlap_score), 4),
                    "score_detail": {
                        "semantic_similarity": round(float(final_score_detail["semantic_similarity"]), 4),
                        "experience_fit": round(float(final_score_detail["experience_fit"]), 4),
                        "seniority_fit": round(float(final_score_detail["seniority_fit"]), 4),
                        "category_fit": round(float(final_score_detail["category_fit"]), 4),
                    },
                    "skill_overlap_detail": {
                        "core_overlap": round(float(skill_overlap_detail["core_overlap"]), 4),
                        "expanded_overlap": round(float(skill_overlap_detail["expanded_overlap"]), 4),
                        "normalized_overlap": round(float(skill_overlap_detail["normalized_overlap"]), 4),
                    },
                })
        
        # Sort by deterministic final score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

matching_service = MatchingService()
