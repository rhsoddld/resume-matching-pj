from __future__ import annotations

import argparse
import hashlib
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
from openai import OpenAI
from pymongo import UpdateOne

from backend.core.database import get_collection
from backend.core.settings import settings
from backend.core.vector_store import CandidateEmbedding, upsert_embeddings
from backend.services.resume_parsing import parse_resume_text
from backend.schemas.candidate import Candidate, ParsedEducation, ParsedExperienceItem, ParsedSection


ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT / "data"

DEFAULT_BATCH_SIZE = 32
DEFAULT_CSV_CHUNK_SIZE = 2000
EMBEDDING_TEXT_CHAR_LIMIT = 4000
HASH_EXCLUDED_INGESTION_FIELDS = {"ingested_at", "normalization_hash", "embedding_hash", "embedding_upserted_at"}

SKILL_NORMALIZATION_MAP = {
    "ms excel": "excel",
    "microsoft excel": "excel",
    "ms office": "microsoft office",
    "mongo db": "mongodb",
    "mongo db-3.2": "mongodb",
    "ssrs": "sql server reporting services",
}

MONTH_NAME_MAP = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}
SEASON_MONTH_MAP = {
    "spring": 3,
    "summer": 6,
    "fall": 9,
    "autumn": 9,
    "winter": 12,
}


client = OpenAI(api_key=settings.openai_api_key)
logger = logging.getLogger(__name__)


@dataclass
class ExistingState:
    normalization_hash: str | None
    embedding_hash: str | None


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


def _clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return None
    return re.sub(r"\s+", " ", text)


def _normalize_identifier(value: object, prefix: str) -> str:
    text = _clean_text(value) or "unknown"
    text = text.replace(".0", "")
    return f"{prefix}-{text}"


def _dedupe_preserve(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _normalize_skill(skill: str) -> str:
    token = re.sub(r"\s+", " ", skill.strip().lower())
    token = token.replace("&", " and ")
    token = re.sub(r"\s+", " ", token).strip()
    return SKILL_NORMALIZATION_MAP.get(token, token)


def _normalize_skill_list(values: Iterable[object]) -> tuple[list[str], list[str]]:
    skills = [_clean_text(v) for v in values]
    raw = _dedupe_preserve([s for s in skills if s is not None])
    normalized = _dedupe_preserve([_normalize_skill(s) for s in raw])
    return raw, normalized


def _normalize_month(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    lowered = text.lower().strip(" ,.;:()[]{}")
    lowered = re.sub(
        r"^(from|since|starting|started|start|beginning|began|as of|effective)\s+",
        "",
        lowered,
    )
    lowered = re.sub(r"\s+", " ", lowered).strip()
    if lowered in {"present", "current", "now"}:
        return "present"
    if lowered in {"00/00", "00/0000", "00/yy", "yy", "unknown", "n/a", "na"}:
        return None

    def _year_month(year: int, month: int) -> str | None:
        if year < 1900 or year > 2100:
            return None
        if month < 1 or month > 12:
            return None
        return f"{year:04d}-{month:02d}"

    match = re.match(r"^(?P<month>\d{1,2})/(?P<year>\d{4})$", lowered)
    if match:
        month = int(match.group("month"))
        year = int(match.group("year"))
        if month == 0:
            month = 1
        normalized = _year_month(year, month)
        if normalized:
            return normalized

    match = re.match(r"^(?P<year>\d{4})/(?P<month>\d{1,2})$", lowered)
    if match:
        year = int(match.group("year"))
        month = int(match.group("month"))
        if month == 0:
            month = 1
        normalized = _year_month(year, month)
        if normalized:
            return normalized

    match = re.match(r"^(?P<season>spring|summer|fall|autumn|winter)\s+(?P<year>\d{4})$", lowered)
    if match:
        season = match.group("season")
        year = int(match.group("year"))
        month = SEASON_MONTH_MAP.get(season)
        if month is not None:
            normalized = _year_month(year, month)
            if normalized:
                return normalized

    match = re.match(
        r"^(?P<month>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+"
        r"(?P<year>\d{4})$",
        lowered,
    )
    if match:
        month = MONTH_NAME_MAP.get(match.group("month"))
        year = int(match.group("year"))
        if month is not None:
            normalized = _year_month(year, month)
            if normalized:
                return normalized

    if re.match(r"^\d{1,2}/yy$", lowered):
        return None

    match = re.match(r"^(?P<year>\d{4})$", lowered)
    if match:
        year = int(match.group("year"))
        normalized = _year_month(year, 1)
        if normalized:
            return normalized

    try:
        from dateparser import parse as date_parse  # type: ignore

        parsed = date_parse(
            lowered,
            settings={
                "PREFER_DAY_OF_MONTH": "first",
                "DATE_ORDER": "MDY",
                "PREFER_DATES_FROM": "past",
            },
        )
        if parsed:
            return parsed.strftime("%Y-%m")
    except Exception:
        pass

    formats = ("%m/%Y", "%Y-%m", "%b %Y", "%B %Y", "%Y")
    for fmt in formats:
        try:
            dt = datetime.strptime(lowered, fmt)
            return dt.strftime("%Y-%m")
        except ValueError:
            continue

    year_match = re.search(r"\b(19\d{2}|20\d{2}|21\d{2})\b", lowered)
    if year_match:
        year = int(year_match.group(1))
        normalized = _year_month(year, 1)
        if normalized:
            return normalized

    return None


def _month_to_datetime(value: str | None, *, default_now: bool) -> datetime | None:
    if not value:
        return None
    if value == "present":
        return datetime.utcnow() if default_now else None

    for fmt in ("%Y-%m", "%Y"):
        try:
            dt = datetime.strptime(value, fmt)
            if fmt == "%Y":
                return dt.replace(month=1)
            return dt
        except ValueError:
            continue
    return None


def _estimate_experience_years(items: Sequence[ParsedExperienceItem]) -> float | None:
    total_months = 0
    for item in items:
        start = _month_to_datetime(item.start_date, default_now=False)
        end = _month_to_datetime(item.end_date, default_now=True)
        if start is None:
            continue
        if end is None:
            end = datetime.utcnow()
        months = (end.year - start.year) * 12 + (end.month - start.month) + 1
        if months > 0:
            total_months += months
    if total_months <= 0:
        return None
    return round(total_months / 12.0, 1)


def _infer_seniority_level(experience_years: float | None) -> str | None:
    if experience_years is None:
        return None
    if experience_years < 2:
        return "junior"
    if experience_years < 5:
        return "mid"
    if experience_years < 8:
        return "senior"
    return "lead"


def _prepare_embedding_text(text: str) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        compact = "empty resume"
    return compact[:EMBEDDING_TEXT_CHAR_LIMIT]


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    payload = [_prepare_embedding_text(text) for text in texts]
    resp = client.embeddings.create(model=settings.openai_embedding_model, input=payload)
    return [item.embedding for item in resp.data]  # type: ignore[no-any-return]


def _extract_sneha_skills(resume_text: str) -> tuple[list[str], list[str]]:
    match = re.search(r"\bskills\b(.*)", resume_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return [], []
    tail = match.group(1)[:1200]
    tokens = re.split(r"[,\n;|]", tail)
    return _normalize_skill_list(tokens[:60])


def _build_embedding_text(
    *,
    name: str | None,
    category: str | None,
    summary: str | None,
    skills: Sequence[str],
    abilities: Sequence[str],
    experience_titles: Sequence[str],
    fallback_text: str | None,
) -> str:
    parts: list[str] = []
    if name:
        parts.append(f"Name: {name}")
    if category:
        parts.append(f"Category: {category}")
    if summary:
        parts.append(f"Summary: {summary}")
    if skills:
        parts.append("Skills: " + "; ".join(skills[:30]))
    if abilities:
        parts.append("Abilities: " + "; ".join(abilities[:30]))
    if experience_titles:
        parts.append("Experience titles: " + "; ".join(experience_titles[:20]))
    if fallback_text and not parts:
        parts.append(fallback_text)
    return _prepare_embedding_text("\n".join(parts))


def _iter_csv_chunks(path: Path, csv_chunk_size: int) -> Iterable[pd.DataFrame]:
    yield from pd.read_csv(path, chunksize=csv_chunk_size)


def _candidate_key(cand: Candidate) -> tuple[str, str]:
    return (cand.source_dataset, cand.candidate_id)


def _normalization_payload(cand: Candidate) -> dict:
    payload = cand.model_dump()
    ingestion = payload.get("ingestion") or {}
    for key in HASH_EXCLUDED_INGESTION_FIELDS:
        ingestion.pop(key, None)
    payload["ingestion"] = ingestion
    return payload


def _compute_normalization_hash(cand: Candidate) -> str:
    payload = _normalization_payload(cand)
    raw = json.dumps(payload, ensure_ascii=True, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _ensure_normalization_hash(cand: Candidate) -> str:
    norm_hash = cand.ingestion.normalization_hash
    if norm_hash:
        return norm_hash
    norm_hash = _compute_normalization_hash(cand)
    cand.ingestion.normalization_hash = norm_hash
    return norm_hash


def _to_parsed_education(records: Sequence) -> list[ParsedEducation]:
    items: list[ParsedEducation] = []
    for record in records:
        items.append(
            ParsedEducation(
                degree=_clean_text(getattr(record, "degree", None)),
                institution=_clean_text(getattr(record, "institution", None)),
                start_date=_normalize_month(getattr(record, "start_date", None)),
                end_date=_normalize_month(getattr(record, "end_date", None)),
                location=_clean_text(getattr(record, "location", None)),
            )
        )
    return items


def _to_parsed_experience(records: Sequence) -> list[ParsedExperienceItem]:
    items: list[ParsedExperienceItem] = []
    for record in records:
        items.append(
            ParsedExperienceItem(
                title=_clean_text(getattr(record, "title", None)),
                company=_clean_text(getattr(record, "company", None)),
                start_date=_normalize_month(getattr(record, "start_date", None)),
                end_date=_normalize_month(getattr(record, "end_date", None)),
                location=_clean_text(getattr(record, "location", None)),
                description=_clean_text(getattr(record, "description", None)),
            )
        )
    return items


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
            skills, normalized_skills = _normalize_skill_list(source_skills)

            education_items = _to_parsed_education(extracted.education)
            experience_items = _to_parsed_experience(extracted.experience)
            experience_years = _estimate_experience_years(experience_items)
            seniority = _infer_seniority_level(experience_years)
            summary = extracted.summary or (resume_text[:280] if resume_text else None)

            parsed = ParsedSection(
                summary=summary,
                skills=skills,
                normalized_skills=normalized_skills,
                abilities=[],
                experience_years=experience_years,
                seniority_level=seniority,
                education=education_items,
                experience_items=experience_items,
            )
            experience_titles = _dedupe_preserve([item.title for item in experience_items if item.title])

            embedding_text = _build_embedding_text(
                name=extracted.name,
                category=category,
                summary=summary,
                skills=normalized_skills,
                abilities=[],
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
                    "parsing_version": f"v3-{parser_mode}-normalized",
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
        skills, normalized_skills = _normalize_skill_list(skill_map.get(pid, []))

        education_items: list[ParsedEducation] = []
        for edu in edu_map.get(pid, []):
            education_items.append(
                ParsedEducation(
                    degree=_clean_text(edu.get("program")),
                    institution=_clean_text(edu.get("institution")),
                    start_date=_normalize_month(edu.get("start_date")),
                    end_date=None,
                    location=_clean_text(edu.get("location")),
                )
            )

        experience_items: list[ParsedExperienceItem] = []
        for exp in exp_map.get(pid, []):
            experience_items.append(
                ParsedExperienceItem(
                    title=_clean_text(exp.get("title")),
                    company=_clean_text(exp.get("firm")),
                    start_date=_normalize_month(exp.get("start_date")),
                    end_date=_normalize_month(exp.get("end_date")),
                    location=_clean_text(exp.get("location")),
                    description=None,
                )
            )

        experience_years = _estimate_experience_years(experience_items)
        seniority = _infer_seniority_level(experience_years)
        location = next((item.location for item in experience_items if item.location), None)
        summary = f"{name} resume profile" if name else None
        experience_titles = _dedupe_preserve([item.title for item in experience_items if item.title])

        parsed = ParsedSection(
            summary=summary,
            skills=skills,
            normalized_skills=normalized_skills,
            abilities=abilities_raw,
            experience_years=experience_years,
            seniority_level=seniority,
            education=education_items,
            experience_items=experience_items,
        )

        embedding_text = _build_embedding_text(
            name=name,
            category=None,
            summary=summary,
            skills=normalized_skills,
            abilities=abilities_raw,
            experience_titles=experience_titles,
            fallback_text=None,
        )

        yield Candidate(
            candidate_id=candidate_id,
            source_dataset="suriyaganesh",
            source_keys={"person_id": pid},
            category=None,
            raw={"structured": True},
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
                "parsing_version": "v3-rule-based-normalized",
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
            _ensure_normalization_hash(cand)
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
        key = _candidate_key(cand)
        prev = existing.get(key)
        prev_norm_hash = prev.normalization_hash if prev else None
        prev_embedding_hash = prev.embedding_hash if prev else None

        needs_mongo_upsert = write_mongo and (force_mongo_upsert or prev_norm_hash != norm_hash)
        needs_embedding = write_milvus and (force_reembed or prev_embedding_hash != norm_hash)

        if needs_mongo_upsert:
            doc = cand.model_dump()
            doc_ingestion = doc.setdefault("ingestion", {})
            doc_ingestion["ingested_at"] = now_iso
            doc_ingestion["normalization_hash"] = norm_hash
            if prev_embedding_hash == norm_hash:
                doc_ingestion["embedding_hash"] = prev_embedding_hash
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
        ops.append(
            UpdateOne(
                {"candidate_id": cand.candidate_id, "source_dataset": cand.source_dataset},
                {
                    "$set": {
                        "ingestion.normalization_hash": norm_hash,
                        "ingestion.embedding_hash": norm_hash,
                        "ingestion.embedding_upserted_at": now_iso,
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
