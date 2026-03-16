from __future__ import annotations

import argparse
import json
import logging
import re
import time
import warnings
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence

# Some parser dependencies emit a noisy compatibility warning on import.
warnings.filterwarnings(
    "ignore",
    message=r"urllib3 .* doesn't match a supported version!",
    category=Warning,
)

import pandas as pd
from pymongo import UpdateOne

from backend.core.database import get_collection
from backend.core.providers import get_openai_client
from backend.core.settings import settings
from backend.core.vector_store import CandidateEmbedding, upsert_embeddings
from backend.services.ingestion.constants import (
    EMBEDDING_TEXT_VERSION,
    EXPERIENCE_YEARS_METHOD,
    NORMALIZATION_VERSION,
    PARSING_VERSION_STRUCTURED,
    PARSING_VERSION_TEMPLATE,
    TAXONOMY_VERSION,
)
from backend.services.ingestion.preprocessing import (
    build_embedding_text as _build_embedding_text_impl,
    clean_text as _clean_text,
    dedupe_preserve as _dedupe_preserve,
    estimate_experience_years as _estimate_experience_years,
    estimate_experience_years_from_text as _estimate_experience_years_from_text,
    extract_sneha_abilities as _extract_sneha_abilities,
    extract_sneha_skills as _extract_sneha_skills,
    impute_category_rule_based as _impute_category_rule_based,
    infer_seniority_level as _infer_seniority_level,
    normalize_identifier as _normalize_identifier,
    normalize_skill_list as _normalize_skill_list,
    prepare_embedding_text as _prepare_embedding_text,
    sanitize_skill_tokens as _sanitize_skill_tokens,
)
from backend.services.ingestion.state import (
    ExistingState,
    candidate_key as _candidate_key,
    ensure_embedding_hash as _ensure_embedding_hash,
    ensure_ingestion_versions as _ensure_ingestion_versions,
    ensure_normalization_hash as _ensure_normalization_hash,
)
from backend.services.ingestion.transformers import (
    build_synthetic_resume_text,
    inject_sneha_category_skill,
    to_parsed_education,
    to_parsed_experience,
)
from backend.services.skill_ontology import RuntimeSkillOntology, SkillNormalizationResult
from backend.services.resume_parsing import parse_resume_text
from backend.schemas.candidate import Candidate, ParsedSection


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"

DEFAULT_BATCH_SIZE = 32
DEFAULT_CSV_CHUNK_SIZE = 2000
EMBEDDING_TEXT_CHAR_LIMIT = 4000

client = get_openai_client()
logger = logging.getLogger(__name__)


def _load_runtime_ontology() -> RuntimeSkillOntology:
    return RuntimeSkillOntology.load_from_config(CONFIG_DIR)


ONTOLOGY = _load_runtime_ontology()


@dataclass
class BatchPlan:
    mongo_ops: list[UpdateOne]
    embed_candidates: list[Candidate]
    mongo_skipped: int
    embed_skipped: int


def _configure_logging() -> None:
    root = logging.getLogger()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    if not root.handlers:
        logging.basicConfig(level=level, format="%(message)s")
    else:
        root.setLevel(level)


def _log_event(event: str, *, level: int = logging.INFO, **fields: object) -> None:
    payload = {"event": event, **fields}
    logger.log(level, json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str))


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    payload = [_prepare_embedding_text(text, char_limit=EMBEDDING_TEXT_CHAR_LIMIT) for text in texts]
    resp = client.embeddings.create(model=settings.openai_embedding_model, input=payload)
    return [item.embedding for item in resp.data]  # type: ignore[no-any-return]


def _apply_skill_normalization(
    *,
    raw_skills: Sequence[object],
    abilities: Sequence[object],
) -> tuple[list[str], SkillNormalizationResult]:
    raw, _ = _normalize_skill_list(raw_skills)
    sanitized = _sanitize_skill_tokens(raw)
    cleaned_raw = sanitized if sanitized else raw
    result = ONTOLOGY.normalize(raw_skills=cleaned_raw, abilities=abilities)
    return cleaned_raw, result


def _extract_text_skill_hints(resume_text: str, *, limit: int = 30) -> list[str]:
    if not resume_text:
        return []
    compact_text = re.sub(r"\s+", " ", resume_text).lower()
    compact = f" {compact_text} "
    hints: list[str] = []
    # Try longer aliases first to avoid picking shorter, ambiguous substrings.
    aliases = sorted(ONTOLOGY.alias_to_canonical.keys(), key=len, reverse=True)
    for alias in aliases:
        if len(alias) < 3:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])"
        if not re.search(pattern, compact):
            continue
        canonical = ONTOLOGY.alias_to_canonical.get(alias, alias)
        hints.append(canonical)
        if len(hints) >= limit:
            break
    return _dedupe_preserve(hints)


def _build_embedding_text(
    *,
    name: str | None,
    category: str | None,
    summary: str | None,
    core_skills: Sequence[str],
    canonical_skills: Sequence[str],
    expanded_skills: Sequence[str],
    capability_phrases: Sequence[str],
    experience_titles: Sequence[str],
    fallback_text: str | None,
) -> str:
    return _build_embedding_text_impl(
        name=name,
        category=category,
        summary=summary,
        core_skills=core_skills,
        canonical_skills=canonical_skills,
        expanded_skills=expanded_skills,
        capability_phrases=capability_phrases,
        experience_titles=experience_titles,
        fallback_text=fallback_text,
        char_limit=EMBEDDING_TEXT_CHAR_LIMIT,
    )


def _iter_csv_chunks(path: Path, csv_chunk_size: int) -> Iterable[pd.DataFrame]:
    yield from pd.read_csv(path, chunksize=csv_chunk_size)


def _upgrade_candidate_to_v2(cand: Candidate) -> Candidate:
    raw_skill_source: Sequence[object] = cand.parsed.skills or cand.parsed.normalized_skills
    raw_skills, skill_norm = _apply_skill_normalization(raw_skills=raw_skill_source, abilities=cand.parsed.abilities)
    cand.parsed.skills = raw_skills
    cand.parsed.normalized_skills = skill_norm.normalized_skills
    cand.parsed.canonical_skills = skill_norm.canonical_skills
    cand.parsed.core_skills = skill_norm.core_skills
    cand.parsed.expanded_skills = skill_norm.expanded_skills
    cand.parsed.capability_phrases = skill_norm.capability_phrases
    cand.parsed.role_candidates = skill_norm.role_candidates
    cand.parsed.review_required_skills = skill_norm.review_required_skills
    cand.parsed.versioned_skills = skill_norm.versioned_skills

    if cand.parsed.experience_items:
        cand.parsed.experience_years = _estimate_experience_years(cand.parsed.experience_items)
        cand.parsed.seniority_level = _infer_seniority_level(cand.parsed.experience_years)

    experience_titles = _dedupe_preserve([item.title for item in cand.parsed.experience_items if item.title])
    fallback_text = cand.raw.get("resume_text") if isinstance(cand.raw, dict) else None
    cand.embedding_text = _build_embedding_text(
        name=cand.metadata.name,
        category=cand.category,
        summary=cand.parsed.summary,
        core_skills=cand.parsed.core_skills,
        canonical_skills=cand.parsed.canonical_skills,
        expanded_skills=cand.parsed.expanded_skills,
        capability_phrases=cand.parsed.capability_phrases,
        experience_titles=experience_titles,
        fallback_text=fallback_text,
    )

    _ensure_ingestion_versions(cand)
    if not cand.ingestion.parsing_version:
        cand.ingestion.parsing_version = (
            PARSING_VERSION_STRUCTURED if cand.source_dataset == "suriyaganesh" else PARSING_VERSION_TEMPLATE.format(parser_mode="hybrid")
        )
    cand.ingestion.alias_applied = skill_norm.alias_applied
    cand.ingestion.taxonomy_applied = skill_norm.taxonomy_applied
    return cand


def iter_sneha(
    limit: int | None = None,
    *,
    csv_chunk_size: int = DEFAULT_CSV_CHUNK_SIZE,
    parser_mode: str = "hybrid",
) -> Iterable[Candidate]:
    path = DATA_DIR / "snehaanbhawal" / "resume-dataset" / "Resume.csv"
    emitted = 0
    for chunk in _iter_csv_chunks(path, csv_chunk_size):
        for _, row in chunk.iterrows():
            candidate_id = _normalize_identifier(row.get("ID"), "sneha")
            raw_id = _clean_text(row.get("ID"))
            resume_text = _clean_text(row.get("Resume_str")) or ""
            resume_html = _clean_text(row.get("Resume_html"))
            category = _clean_text(row.get("Category"))

            extracted = parse_resume_text(resume_text, parser_mode=parser_mode)
            fallback_skills, _ = _extract_sneha_skills(resume_text)
            source_skills = extracted.skills if extracted.skills else fallback_skills
            if not source_skills:
                source_skills = _extract_text_skill_hints(resume_text)

            education_items = to_parsed_education(extracted.education)
            experience_items = to_parsed_experience(extracted.experience)
            summary = extracted.summary or (resume_text[:280] if resume_text else None)
            abilities = _extract_sneha_abilities(
                resume_text=resume_text,
                summary=summary,
                experience_items=experience_items,
            )
            raw_skills, skill_norm = _apply_skill_normalization(raw_skills=source_skills, abilities=abilities)

            experience_years = _estimate_experience_years(experience_items)
            if experience_years is None:
                experience_years = _estimate_experience_years_from_text(resume_text)
            seniority = _infer_seniority_level(experience_years)

            parsed = ParsedSection(
                summary=summary,
                skills=raw_skills,
                normalized_skills=skill_norm.normalized_skills,
                abilities=abilities,
                canonical_skills=skill_norm.canonical_skills,
                core_skills=skill_norm.core_skills,
                expanded_skills=skill_norm.expanded_skills,
                capability_phrases=skill_norm.capability_phrases,
                role_candidates=skill_norm.role_candidates,
                review_required_skills=skill_norm.review_required_skills,
                versioned_skills=skill_norm.versioned_skills,
                experience_years=experience_years,
                seniority_level=seniority,
                education=education_items,
                experience_items=experience_items,
            )

            inject_sneha_category_skill(parsed=parsed, category=category, ontology=ONTOLOGY)
            experience_titles = _dedupe_preserve([item.title for item in experience_items if item.title])

            embedding_text = _build_embedding_text(
                name=extracted.name,
                category=category,
                summary=summary,
                core_skills=parsed.core_skills,
                canonical_skills=parsed.canonical_skills,
                expanded_skills=parsed.expanded_skills,
                capability_phrases=parsed.capability_phrases,
                experience_titles=experience_titles,
                fallback_text=resume_text,
            )

            yield Candidate(
                candidate_id=candidate_id,
                source_dataset="snehaanbhawal",
                source_keys={"ID": raw_id},
                category=category,
                raw={"resume_text": resume_text, "resume_html": resume_html},
                parsed=parsed,
                metadata={
                    "name": extracted.name,
                    "email": extracted.email,
                    "phone": extracted.phone,
                },
                embedding_text=embedding_text,
                ingestion={
                    "ingested_at": None,
                    "parsing_version": PARSING_VERSION_TEMPLATE.format(parser_mode=parser_mode),
                    "normalization_version": NORMALIZATION_VERSION,
                    "taxonomy_version": TAXONOMY_VERSION,
                    "embedding_text_version": EMBEDDING_TEXT_VERSION,
                    "experience_years_method": EXPERIENCE_YEARS_METHOD,
                    "alias_applied": skill_norm.alias_applied,
                    "taxonomy_applied": skill_norm.taxonomy_applied,
                    "has_structured_enrichment": False,
                },
            )
            emitted += 1
            if limit is not None and emitted >= limit:
                return


def _read_people_rows(path: Path, *, limit_people: int | None, csv_chunk_size: int) -> list[dict]:
    rows: list[dict] = []
    for chunk in _iter_csv_chunks(path, csv_chunk_size):
        for row in chunk.to_dict(orient="records"):
            rows.append(row)
            if limit_people is not None and len(rows) >= limit_people:
                return rows
    return rows


def _load_grouped_values(
    path: Path,
    *,
    pid_set: set[int],
    value_column: str,
    csv_chunk_size: int,
) -> dict[int, list[object]]:
    grouped: dict[int, list[object]] = {}
    if not pid_set:
        return grouped
    for chunk in pd.read_csv(path, usecols=["person_id", value_column], chunksize=csv_chunk_size):
        chunk = chunk[chunk["person_id"].isin(pid_set)]
        if chunk.empty:
            continue
        for pid, values in chunk.groupby("person_id", sort=False)[value_column]:
            grouped.setdefault(int(pid), []).extend(values.tolist())
    return grouped


def _load_grouped_records(
    path: Path,
    *,
    pid_set: set[int],
    record_columns: list[str],
    csv_chunk_size: int,
) -> dict[int, list[dict]]:
    grouped: dict[int, list[dict]] = {}
    if not pid_set:
        return grouped
    usecols = ["person_id", *record_columns]
    for chunk in pd.read_csv(path, usecols=usecols, chunksize=csv_chunk_size):
        chunk = chunk[chunk["person_id"].isin(pid_set)]
        if chunk.empty:
            continue
        for pid, grp in chunk.groupby("person_id", sort=False):
            records = grp.drop(columns=["person_id"]).to_dict(orient="records")
            grouped.setdefault(int(pid), []).extend(records)
    return grouped


def iter_suri(limit_people: int = 3000, *, csv_chunk_size: int = DEFAULT_CSV_CHUNK_SIZE) -> Iterable[Candidate]:
    base = DATA_DIR / "suriyaganesh" / "resume-dataset-structured"
    people_rows = _read_people_rows(
        base / "01_people.csv",
        limit_people=limit_people,
        csv_chunk_size=csv_chunk_size,
    )
    pid_set = {int(row["person_id"]) for row in people_rows}

    abil_map = _load_grouped_values(
        base / "02_abilities.csv",
        pid_set=pid_set,
        value_column="ability",
        csv_chunk_size=csv_chunk_size,
    )
    skill_map = _load_grouped_values(
        base / "05_person_skills.csv",
        pid_set=pid_set,
        value_column="skill",
        csv_chunk_size=csv_chunk_size,
    )
    edu_map = _load_grouped_records(
        base / "03_education.csv",
        pid_set=pid_set,
        record_columns=["institution", "program", "start_date", "location"],
        csv_chunk_size=csv_chunk_size,
    )
    exp_map = _load_grouped_records(
        base / "04_experience.csv",
        pid_set=pid_set,
        record_columns=["title", "firm", "start_date", "end_date", "location"],
        csv_chunk_size=csv_chunk_size,
    )

    for row in people_rows:
        pid = int(row["person_id"])
        candidate_id = f"suri-{pid}"
        name = _clean_text(row.get("name"))
        email = _clean_text(row.get("email"))
        phone = _clean_text(row.get("phone"))
        linkedin = _clean_text(row.get("linkedin"))

        abilities_raw, _ = _normalize_skill_list(abil_map.get(pid, []))
        raw_skills, skill_norm = _apply_skill_normalization(raw_skills=skill_map.get(pid, []), abilities=abilities_raw)

        education_records = [
            {
                "degree": edu.get("program"),
                "institution": edu.get("institution"),
                "start_date": edu.get("start_date"),
                "end_date": None,
                "location": edu.get("location"),
            }
            for edu in edu_map.get(pid, [])
        ]
        education_items = to_parsed_education(education_records)

        experience_records = [
            {
                "title": exp.get("title"),
                "company": exp.get("firm"),
                "start_date": exp.get("start_date"),
                "end_date": exp.get("end_date"),
                "location": exp.get("location"),
                "description": None,
            }
            for exp in exp_map.get(pid, [])
        ]
        experience_items = to_parsed_experience(experience_records)

        experience_years = _estimate_experience_years(experience_items)
        seniority = _infer_seniority_level(experience_years)
        location = next((item.location for item in experience_items if item.location), None)
        summary = f"{name} resume profile" if name else None
        experience_titles = _dedupe_preserve([item.title for item in experience_items if item.title])
        
        parsed = ParsedSection(
            summary=summary,
            skills=raw_skills,
            normalized_skills=skill_norm.normalized_skills,
            abilities=abilities_raw,
            canonical_skills=skill_norm.canonical_skills,
            core_skills=skill_norm.core_skills,
            expanded_skills=skill_norm.expanded_skills,
            capability_phrases=skill_norm.capability_phrases,
            role_candidates=skill_norm.role_candidates,
            review_required_skills=skill_norm.review_required_skills,
            versioned_skills=skill_norm.versioned_skills,
            experience_years=experience_years,
            seniority_level=seniority,
            education=education_items,
            experience_items=experience_items,
        )
        
        # --- Rule-based Category Imputation ---
        category = _impute_category_rule_based(experience_titles, parsed.core_skills)
        
        synthetic_resume_text = build_synthetic_resume_text(
            name=name,
            category=category,
            skills=parsed.skills,
            abilities=parsed.abilities,
            experience_items=experience_items,
            education_items=education_items,
        )

        embedding_text = _build_embedding_text(
            name=name,
            category=category,
            summary=summary,
            core_skills=parsed.core_skills,
            canonical_skills=parsed.canonical_skills,
            expanded_skills=parsed.expanded_skills,
            capability_phrases=parsed.capability_phrases,
            experience_titles=experience_titles,
            fallback_text=synthetic_resume_text,
        )

        yield Candidate(
            candidate_id=candidate_id,
            source_dataset="suriyaganesh",
            source_keys={"person_id": pid},
            category=category,
            raw={"resume_text": synthetic_resume_text},
            parsed=parsed,
            metadata={
                "name": name,
                "location": location,
                "email": email,
                "phone": phone,
                "linkedin": linkedin,
            },
            embedding_text=embedding_text,
            ingestion={
                "ingested_at": None,
                "parsing_version": PARSING_VERSION_STRUCTURED,
                "normalization_version": NORMALIZATION_VERSION,
                "taxonomy_version": TAXONOMY_VERSION,
                "embedding_text_version": EMBEDDING_TEXT_VERSION,
                "experience_years_method": EXPERIENCE_YEARS_METHOD,
                "alias_applied": skill_norm.alias_applied,
                "taxonomy_applied": skill_norm.taxonomy_applied,
                "has_structured_enrichment": True,
            },
        )


def iter_candidates(
    source: str,
    *,
    sneha_limit: int | None,
    suri_limit: int,
    csv_chunk_size: int,
    parser_mode: str,
) -> Iterable[Candidate]:
    if source in ("sneha", "all"):
        yield from iter_sneha(limit=sneha_limit, csv_chunk_size=csv_chunk_size, parser_mode=parser_mode)
    if source in ("suri", "all"):
        yield from iter_suri(limit_people=suri_limit, csv_chunk_size=csv_chunk_size)


def iter_candidates_from_mongo(source: str, *, sneha_limit: int | None, suri_limit: int) -> Iterable[Candidate]:
    coll = get_collection("candidates")
    source_map = {
        "sneha": ("snehaanbhawal", sneha_limit),
        "suri": ("suriyaganesh", suri_limit),
    }
    keys = ["sneha", "suri"] if source == "all" else [source]

    for key in keys:
        dataset_name, limit = source_map[key]
        cursor = coll.find({"source_dataset": dataset_name})
        if limit is not None:
            cursor = cursor.limit(limit)
        for doc in cursor:
            doc.pop("_id", None)
            cand = Candidate.model_validate(doc)
            cand = _upgrade_candidate_to_v2(cand)
            _ensure_normalization_hash(cand)
            _ensure_embedding_hash(cand)
            yield cand


def _chunked(items: Iterable[Candidate], size: int) -> Iterator[list[Candidate]]:
    batch: list[Candidate] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def _lookup_existing_state(batch: Sequence[Candidate]) -> dict[tuple[str, str], ExistingState]:
    if not batch:
        return {}
    coll = get_collection("candidates")

    grouped: dict[str, list[str]] = {}
    for cand in batch:
        grouped.setdefault(cand.source_dataset, []).append(cand.candidate_id)

    state_map: dict[tuple[str, str], ExistingState] = {}
    for dataset, candidate_ids in grouped.items():
        docs = coll.find(
            {"source_dataset": dataset, "candidate_id": {"$in": candidate_ids}},
            {"candidate_id": 1, "source_dataset": 1, "ingestion.normalization_hash": 1, "ingestion.embedding_hash": 1},
        )
        for doc in docs:
            ingestion = doc.get("ingestion") or {}
            key = (str(doc.get("source_dataset")), str(doc.get("candidate_id")))
            state_map[key] = ExistingState(
                normalization_hash=ingestion.get("normalization_hash"),
                embedding_hash=ingestion.get("embedding_hash"),
            )
    return state_map


def _build_batch_plan(
    batch: Sequence[Candidate],
    *,
    existing: dict[tuple[str, str], ExistingState],
    write_mongo: bool,
    write_milvus: bool,
    force_mongo_upsert: bool,
    force_reembed: bool,
) -> BatchPlan:
    mongo_ops: list[UpdateOne] = []
    embed_candidates: list[Candidate] = []
    mongo_skipped = 0
    embed_skipped = 0

    now_iso = datetime.utcnow().isoformat()

    for cand in batch:
        norm_hash = _ensure_normalization_hash(cand)
        emb_hash = _ensure_embedding_hash(cand)
        key = _candidate_key(cand)
        prev = existing.get(key)
        prev_norm_hash = prev.normalization_hash if prev else None
        prev_embedding_hash = prev.embedding_hash if prev else None

        needs_mongo_upsert = write_mongo and (force_mongo_upsert or prev_norm_hash != norm_hash)
        needs_embedding = write_milvus and (force_reembed or prev_embedding_hash != emb_hash)

        if needs_mongo_upsert:
            doc = cand.model_dump()
            doc_ingestion = doc.setdefault("ingestion", {})
            doc_ingestion["ingested_at"] = now_iso
            doc_ingestion["normalization_hash"] = norm_hash
            if prev_embedding_hash == emb_hash:
                doc_ingestion["embedding_hash"] = emb_hash
            else:
                doc_ingestion["embedding_hash"] = None
                doc_ingestion["embedding_upserted_at"] = None
            mongo_ops.append(
                UpdateOne(
                    {"candidate_id": cand.candidate_id, "source_dataset": cand.source_dataset},
                    {"$set": doc},
                    upsert=True,
                )
            )
        elif write_mongo:
            mongo_skipped += 1

        if needs_embedding:
            embed_candidates.append(cand)
        elif write_milvus:
            embed_skipped += 1

    return BatchPlan(
        mongo_ops=mongo_ops,
        embed_candidates=embed_candidates,
        mongo_skipped=mongo_skipped,
        embed_skipped=embed_skipped,
    )


def _apply_mongo_ops(ops: Sequence[UpdateOne], *, dry_run: bool) -> int:
    if not ops:
        return 0
    if dry_run:
        return len(ops)
    coll = get_collection("candidates")
    coll.bulk_write(list(ops), ordered=False)
    return len(ops)


def _mark_embedding_synced(cands: Sequence[Candidate], *, dry_run: bool) -> int:
    if not cands:
        return 0
    if dry_run:
        return len(cands)

    coll = get_collection("candidates")
    now_iso = datetime.utcnow().isoformat()
    ops: list[UpdateOne] = []
    for cand in cands:
        norm_hash = _ensure_normalization_hash(cand)
        emb_hash = _ensure_embedding_hash(cand)
        ops.append(
            UpdateOne(
                {"candidate_id": cand.candidate_id, "source_dataset": cand.source_dataset},
                {
                    "$set": {
                        "ingestion.normalization_hash": norm_hash,
                        "ingestion.embedding_hash": emb_hash,
                        "ingestion.embedding_upserted_at": now_iso,
                        "ingestion.normalization_version": cand.ingestion.normalization_version,
                        "ingestion.taxonomy_version": cand.ingestion.taxonomy_version,
                        "ingestion.embedding_text_version": cand.ingestion.embedding_text_version,
                        "ingestion.experience_years_method": cand.ingestion.experience_years_method,
                        "ingestion.alias_applied": cand.ingestion.alias_applied,
                        "ingestion.taxonomy_applied": cand.ingestion.taxonomy_applied,
                    }
                },
                upsert=False,
            )
        )
    if ops:
        coll.bulk_write(ops, ordered=False)
    return len(ops)


def _upsert_milvus_batch(batch: Sequence[Candidate], *, dry_run: bool) -> int:
    if not batch:
        return 0
    if dry_run:
        return len(batch)

    texts = [cand.embedding_text or cand.raw.get("resume_text", "") for cand in batch]
    vectors = embed_texts(texts)
    embeddings: list[CandidateEmbedding] = []
    for cand, vector in zip(batch, vectors, strict=True):
        embeddings.append(
            CandidateEmbedding(
                candidate_id=cand.candidate_id,
                source_dataset=cand.source_dataset,
                category=cand.category,
                experience_years=cand.parsed.experience_years,
                seniority_level=cand.parsed.seniority_level,
                vector=vector,
            )
        )
    upsert_embeddings(embeddings)
    return len(batch)


def run_ingestion(
    candidates: Iterable[Candidate],
    *,
    write_mongo: bool,
    write_milvus: bool,
    batch_size: int,
    force_mongo_upsert: bool,
    force_reembed: bool,
    dry_run: bool,
) -> None:
    start = time.perf_counter()
    seen = 0
    mongo_upserted = 0
    mongo_skipped = 0
    embedded = 0
    embed_skipped = 0

    for batch in _chunked(candidates, batch_size):
        seen += len(batch)
        existing = _lookup_existing_state(batch) if (write_mongo or write_milvus) and not dry_run else {}
        plan = _build_batch_plan(
            batch,
            existing=existing,
            write_mongo=write_mongo,
            write_milvus=write_milvus,
            force_mongo_upsert=force_mongo_upsert,
            force_reembed=force_reembed,
        )

        mongo_upserted += _apply_mongo_ops(plan.mongo_ops, dry_run=dry_run)
        mongo_skipped += plan.mongo_skipped

        embedded_now = _upsert_milvus_batch(plan.embed_candidates, dry_run=dry_run)
        embedded += embedded_now
        embed_skipped += plan.embed_skipped
        if write_milvus:
            _mark_embedding_synced(plan.embed_candidates, dry_run=dry_run)

        _log_event(
            "ingest_batch_progress",
            seen=seen,
            mongo_upserted=mongo_upserted,
            mongo_skipped=mongo_skipped,
            embedded=embedded,
            embed_skipped=embed_skipped,
        )

    elapsed = time.perf_counter() - start
    mode = "DRY-RUN" if dry_run else "RUN"
    _log_event(
        "ingest_complete",
        mode=mode,
        seen=seen,
        mongo_upserted=mongo_upserted,
        mongo_skipped=mongo_skipped,
        embedded=embedded,
        embed_skipped=embed_skipped,
        elapsed_sec=round(elapsed, 2),
    )


def main() -> None:
    _configure_logging()
    parser = argparse.ArgumentParser(description="Ingest resume datasets into MongoDB and/or Milvus.")
    parser.add_argument(
        "--source",
        choices=["sneha", "suri", "all"],
        default="all",
        help="Which dataset to ingest.",
    )
    parser.add_argument(
        "--target",
        choices=["all", "mongo", "milvus"],
        default="all",
        help="Where to write data.",
    )
    parser.add_argument(
        "--milvus-from-mongo",
        action="store_true",
        help="When target=milvus, read candidate documents from MongoDB instead of raw CSV files.",
    )
    parser.add_argument(
        "--force-mongo-upsert",
        action="store_true",
        help="Force Mongo upsert even when normalization_hash is unchanged.",
    )
    parser.add_argument(
        "--force-reembed",
        action="store_true",
        help="Force re-embedding even when embedding_hash matches normalization_hash.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Compute normalization and batch plan without writing MongoDB/Milvus.",
    )
    parser.add_argument(
        "--parser-mode",
        choices=["rule", "spacy", "hybrid"],
        default="hybrid",
        help="Parsing mode for unstructured resumes (Sneha dataset). hybrid = rule + spaCy fallback.",
    )
    parser.add_argument(
        "--csv-chunk-size",
        type=int,
        default=DEFAULT_CSV_CHUNK_SIZE,
        help="Chunk size for CSV streaming reads.",
    )
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE, help="Batch size for ingestion.")
    parser.add_argument("--sneha-limit", type=int, default=None, help="Optional limit for sneha dataset rows.")
    parser.add_argument("--suri-limit", type=int, default=3000, help="Max people from structured dataset.")
    args = parser.parse_args()

    write_mongo = args.target in {"all", "mongo"}
    write_milvus = args.target in {"all", "milvus"}

    if args.batch_size <= 0:
        raise ValueError("--batch-size must be greater than 0")
    if args.csv_chunk_size <= 0:
        raise ValueError("--csv-chunk-size must be greater than 0")

    if write_milvus and not write_mongo and args.milvus_from_mongo:
        candidates = iter_candidates_from_mongo(
            args.source,
            sneha_limit=args.sneha_limit,
            suri_limit=args.suri_limit,
        )
    else:
        candidates = iter_candidates(
            args.source,
            sneha_limit=args.sneha_limit,
            suri_limit=args.suri_limit,
            csv_chunk_size=args.csv_chunk_size,
            parser_mode=args.parser_mode,
        )

    run_ingestion(
        candidates,
        write_mongo=write_mongo,
        write_milvus=write_milvus,
        batch_size=args.batch_size,
        force_mongo_upsert=args.force_mongo_upsert,
        force_reembed=args.force_reembed,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
