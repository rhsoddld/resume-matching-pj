import logging
from typing import List

from backend.core.vector_store import search_embeddings
from backend.repositories.mongo_repo import get_candidate_by_id

logger = logging.getLogger(__name__)

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
                results.append({
                    "candidate_id": hit["candidate_id"],
                    "category": hit.get("category"),
                    "summary": parsed.get("summary"),
                    "skills": parsed.get("skills", []),
                    "normalized_skills": parsed.get("normalized_skills", []),
                    "experience_years": hit.get("experience_years"),
                    "seniority_level": hit.get("seniority_level"),
                    "score": hit["score"]
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

matching_service = MatchingService()
