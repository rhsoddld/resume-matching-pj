from __future__ import annotations

import json
import logging
import math
from typing import Any

from backend.core.providers import get_openai_client
from backend.core.settings import settings


logger = logging.getLogger(__name__)


class CrossEncoderRerankService:
    """
    Optional reranking layer over retrieved candidates.
    Uses an LLM as a cross-encoder-style relevance scorer over (JD, candidate snippet) pairs.
    """

    def rerank(
        self,
        *,
        job_description: str,
        enriched_hits: list[tuple[dict[str, Any], dict[str, Any]]],
        top_k: int,
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        if len(enriched_hits) <= 1:
            return enriched_hits[:top_k]

        candidates_payload = self._build_candidates_payload(enriched_hits)
        scores = self._score_candidates(job_description=job_description, candidates=candidates_payload)
        if not scores:
            return enriched_hits[:top_k]

        score_by_id = {item["candidate_id"]: float(item["relevance"]) for item in scores if item.get("candidate_id")}
        reranked: list[tuple[dict[str, Any], dict[str, Any], float]] = []
        for hit, doc in enriched_hits:
            candidate_id = hit.get("candidate_id")
            if not candidate_id:
                continue
            rerank_score = score_by_id.get(candidate_id)
            if rerank_score is None:
                rerank_score = float(hit.get("fusion_score", hit.get("score", 0.0)))
            fusion_score = float(hit.get("fusion_score", 0.0))
            blended = (0.75 * rerank_score) + (0.25 * fusion_score)
            updated_hit = dict(hit)
            updated_hit["rerank_score"] = round(rerank_score, 4)
            updated_hit["rerank_blended_score"] = round(blended, 4)
            reranked.append((updated_hit, doc, blended))

        reranked.sort(key=lambda item: item[2], reverse=True)
        return [(hit, doc) for hit, doc, _ in reranked[:top_k]]

    def _score_candidates(self, *, job_description: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        mode = (settings.rerank_mode or "embedding").strip().lower()
        if mode == "llm":
            return self._score_candidates_llm(job_description=job_description, candidates=candidates)
        return self._score_candidates_embedding(job_description=job_description, candidates=candidates)

    def _score_candidates_embedding(self, *, job_description: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not candidates:
            return []
        try:
            client = get_openai_client()
            candidate_texts = [self._candidate_text_for_embedding(item) for item in candidates]
            # One batch request keeps latency predictable and enables a fine-tuned embedding model swap via env.
            response = client.embeddings.create(
                model=settings.rerank_embedding_model,
                input=[job_description, *candidate_texts],
            )
            vectors = [row.embedding for row in response.data]
            if len(vectors) != len(candidate_texts) + 1:
                return []
            query_vector = vectors[0]
            out: list[dict[str, Any]] = []
            for idx, candidate in enumerate(candidates):
                candidate_id = candidate.get("candidate_id")
                if not isinstance(candidate_id, str) or not candidate_id:
                    continue
                similarity = self._cosine_similarity(query_vector, vectors[idx + 1])
                # Cosine [-1,1] -> [0,1]
                relevance = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
                out.append({"candidate_id": candidate_id, "relevance": round(relevance, 6)})
            return out
        except Exception:
            logger.exception("embedding_rerank_failed")
            return []

    def _score_candidates_llm(self, *, job_description: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        system_prompt = (
            "You are a retrieval reranker for hiring. "
            "Score each candidate for relevance to the job description from 0.0 to 1.0. "
            "Return strict JSON only."
        )
        user_payload = {
            "task": "rerank_candidates",
            "output_schema": {
                "scores": [{"candidate_id": "string", "relevance": "float_0_to_1"}]
            },
            "job_description": job_description,
            "candidates": candidates,
        }
        try:
            client = get_openai_client()
            completion = client.chat.completions.create(
                model=settings.rerank_model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
                ],
            )
            raw_content = completion.choices[0].message.content if completion.choices else None
            payload = self._safe_json_load(raw_content)
            rows = payload.get("scores", [])
            if not isinstance(rows, list):
                return []
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for row in rows:
                if not isinstance(row, dict):
                    continue
                candidate_id = row.get("candidate_id")
                relevance = row.get("relevance")
                if not isinstance(candidate_id, str):
                    continue
                if candidate_id in seen:
                    continue
                try:
                    score = float(relevance)
                except Exception:
                    continue
                seen.add(candidate_id)
                out.append({"candidate_id": candidate_id, "relevance": max(0.0, min(1.0, score))})
            return out
        except Exception:
            logger.exception("cross_encoder_rerank_failed")
            return []

    @staticmethod
    def _candidate_text_for_embedding(candidate: dict[str, Any]) -> str:
        skills = candidate.get("skills") or []
        if not isinstance(skills, list):
            skills = []
        skill_text = " ".join(str(skill).strip().lower() for skill in skills if isinstance(skill, str) and skill.strip())
        summary = str(candidate.get("summary") or "").strip()
        category = str(candidate.get("category") or "").strip()
        seniority = str(candidate.get("seniority_level") or "").strip()
        experience = candidate.get("experience_years")
        exp_text = str(experience) if isinstance(experience, (int, float)) else ""
        return " ".join(part for part in [summary, skill_text, category, seniority, exp_text] if part).strip()

    @staticmethod
    def _cosine_similarity(a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(float(x) * float(y) for x, y in zip(a, b))
        norm_a = math.sqrt(sum(float(x) * float(x) for x in a))
        norm_b = math.sqrt(sum(float(y) * float(y) for y in b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm_a * norm_b)))

    @staticmethod
    def _build_candidates_payload(enriched_hits: list[tuple[dict[str, Any], dict[str, Any]]]) -> list[dict[str, Any]]:
        payload: list[dict[str, Any]] = []
        for hit, doc in enriched_hits:
            candidate_id = hit.get("candidate_id")
            if not candidate_id:
                continue
            parsed = doc.get("parsed", {})
            parsed = parsed if isinstance(parsed, dict) else {}
            summary = str(parsed.get("summary") or "").strip()
            skills = parsed.get("normalized_skills") or parsed.get("skills") or []
            if not isinstance(skills, list):
                skills = []
            normalized_skills = [str(skill).strip().lower() for skill in skills if isinstance(skill, str)][:12]
            payload.append(
                {
                    "candidate_id": candidate_id,
                    "category": hit.get("category"),
                    "experience_years": hit.get("experience_years"),
                    "seniority_level": hit.get("seniority_level"),
                    "summary": summary[:320],
                    "skills": normalized_skills,
                }
            )
        return payload

    @staticmethod
    def _safe_json_load(raw_content: Any) -> dict[str, Any]:
        if isinstance(raw_content, str):
            content = raw_content.strip()
            if not content:
                return {}
            try:
                parsed = json.loads(content)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}
        if isinstance(raw_content, dict):
            return raw_content
        return {}


cross_encoder_rerank_service = CrossEncoderRerankService()
