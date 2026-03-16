from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


logger = logging.getLogger(__name__)
_SPACY_NLP = None
_SPACY_LOAD_ATTEMPTED = False
_SPACY_RUNTIME_DISABLED = False

EMAIL_PATTERN = re.compile(r"([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})")
PHONE_PATTERN = re.compile(r"(\+?\d[\d\-\s()]{7,}\d)")
MONTH_TOKEN = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
SEASON_TOKEN = r"(?:Spring|Summer|Fall|Autumn|Winter)"
DATE_TOKEN = rf"(?:\d{{1,2}}/\d{{4}}|\d{{4}}/\d{{1,2}}|{MONTH_TOKEN}\s+\d{{4}}|{SEASON_TOKEN}\s+\d{{4}}|\d{{4}})"
DATE_TOKEN_PATTERN = re.compile(rf"\b({DATE_TOKEN})\b", flags=re.IGNORECASE)
DATE_RANGE_PATTERN = re.compile(
    rf"(?P<start>{DATE_TOKEN})\s*(?:to|-|–|—|－)\s*(?P<end>(?:Present|Current|Now|{DATE_TOKEN}))",
    flags=re.IGNORECASE,
)

SECTION_ALIASES = {
    "summary": {"summary", "professional summary", "profile", "objective"},
    "skills": {"skills", "technical skills", "core skills", "expertise", "core qualifications", "qualifications"},
    "education": {"education", "academic background", "qualifications", "education and training", "academic credentials"},
    "experience": {"experience", "work experience", "employment history", "professional experience"},
}

DEGREE_KEYWORDS = (
    "bachelor",
    "master",
    "phd",
    "doctor",
    "mba",
    "b.sc",
    "bsc",
    "m.sc",
    "msc",
    "diploma",
    "degree",
)

SKILL_SPLIT_PATTERN = re.compile(r"[,;\n|•·]+")
SPACY_CHAR_LIMIT = 80_000

# Tokens that look like conjunctions / sentence fragments rather than skills.
_SKILL_NOISE_PREFIXES = ("and ", "or ", "with ", "the ", "a ", "an ", "to ", "in ", "of ", "for ", "type ", "provide ")
_SKILL_NOISE_SUBSTRINGS = ("bilingual", "languages:", "language:", "proficient in", "including",
                            "such as", "etc.", "experience in", "knowledge of", " and ", " or ",
                            "background in", "10-key", "wpm", "consisting of", "evolved", ".com",
                            "as well as", "understanding of", "ability to", "familiarity with")
_SKILL_MAX_CHARS = 50   # single skills are rarely longer than 50 chars
_SKILL_MIN_CHARS = 2


def _is_valid_skill(token: str) -> bool:
    """Return True if token looks like a real skill name, not sentence noise."""
    t = token.strip()
    if len(t) < _SKILL_MIN_CHARS or len(t) > _SKILL_MAX_CHARS:
        return False
    tl = t.lower()
    if any(tl.startswith(p) for p in _SKILL_NOISE_PREFIXES):
        return False
    if any(sub in tl for sub in _SKILL_NOISE_SUBSTRINGS):
        return False
    # Reject tokens that are mostly punctuation / numbers
    alpha_chars = sum(c.isalpha() for c in t)
    if alpha_chars < 2:
        return False
    return True

@dataclass
class EducationRecord:
    degree: str | None = None
    institution: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None


@dataclass
class ExperienceRecord:
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    location: str | None = None
    description: str | None = None


@dataclass
class ResumeExtraction:
    summary: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    skills: list[str] = field(default_factory=list)
    education: list[EducationRecord] = field(default_factory=list)
    experience: list[ExperienceRecord] = field(default_factory=list)
    career_trajectory: dict = field(default_factory=dict)
    sections: dict[str, str] = field(default_factory=dict)


def _clean_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def _dedupe_preserve(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        v = _clean_line(value)
        if not v:
            continue
        key = v.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(v)
    return out


def _normalize_header(line: str) -> str | None:
    normalized = re.sub(r"[^a-zA-Z ]+", "", line).strip().lower()
    if not normalized:
        return None
    for canonical, aliases in SECTION_ALIASES.items():
        if normalized in aliases:
            return canonical
    return None


def split_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {"root": []}
    current = "root"
    for raw_line in text.splitlines():
        line = _clean_line(raw_line)
        if not line:
            continue
        header = _normalize_header(line)
        if header and len(line) <= 45:
            current = header
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(line)
    return {key: "\n".join(lines).strip() for key, lines in sections.items() if lines}


def _extract_name(text: str, sections: dict[str, str]) -> str | None:
    # Keywords that commonly appear in early lines but are NOT names.
    _NON_NAME_TOKENS = (
        "resume", "curriculum", "profile", "@", "training", "trainings",
        "summary", "objective", "skills", "experience", "education",
        "professional", "career", "highlights", "overview", "served",
        "developed", "managed", "focused", "driven", "dedicated",
        "specialist", "manager", "director", "coordinator",
    )
    first_lines = sections.get("root", text).splitlines()[:6]
    for line in first_lines:
        cleaned = _clean_line(line)
        if not cleaned:
            continue
        lower = cleaned.lower()
        if any(token in lower for token in _NON_NAME_TOKENS):
            continue
        words = cleaned.split()
        # Typical names are 2-4 words, all capitalized-ish, no digits, no special chars
        if not (2 <= len(words) <= 4):
            continue
        if re.search(r"[\d@:()/\\<>|]", cleaned):
            continue
        # Reject if any word is all-uppercase and longer than 5 chars (likely acronym/section header)
        if any(w.isupper() and len(w) > 5 for w in words):
            continue
        return cleaned.title()
    return None


def _extract_contacts(text: str) -> tuple[str | None, str | None]:
    email_match = EMAIL_PATTERN.search(text)
    phone_match = PHONE_PATTERN.search(text)
    email = email_match.group(1) if email_match else None
    phone = _clean_line(phone_match.group(1)) if phone_match else None
    return email, phone


def _extract_skills_regex(sections: dict[str, str], text: str) -> list[str]:
    skills_text = sections.get("skills")
    if not skills_text:
        match = re.search(
            r"\b(?:skills?|technical skills?|core qualifications?|qualifications?|highlights?)\b[:\s\-]*(.*)",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            skills_text = match.group(1)[:1500]
    if not skills_text:
        return []
    parts = SKILL_SPLIT_PATTERN.split(skills_text)
    return _dedupe_preserve(p for p in parts[:120] if _is_valid_skill(p))


def _extract_education_regex(sections: dict[str, str]) -> list[EducationRecord]:
    text = sections.get("education", "")
    if not text:
        return []
    records: list[EducationRecord] = []
    for line in text.splitlines():
        entry = _clean_line(line)
        if not entry:
            continue
        lower = entry.lower()
        if not any(token in lower for token in DEGREE_KEYWORDS):
            continue
        date_match = DATE_TOKEN_PATTERN.search(entry)
        records.append(
            EducationRecord(
                degree=entry,
                institution=None,
                start_date=date_match.group(1) if date_match else None,
                end_date=None,
                location=None,
            )
        )
    return records


def _extract_education_global(text: str) -> list[EducationRecord]:
    records: list[EducationRecord] = []
    cleaned = re.sub(r"\s+", " ", text)
    for match in re.finditer(
        r"((?:Bachelor|Master|PhD|Doctor|MBA|B\.Sc|M\.Sc|Diploma|Degree)[^.;]{0,180})",
        cleaned,
        flags=re.IGNORECASE,
    ):
        chunk = _clean_line(match.group(1))
        date_match = DATE_TOKEN_PATTERN.search(chunk)
        records.append(
            EducationRecord(
                degree=chunk,
                institution=None,
                start_date=date_match.group(1) if date_match else None,
            )
        )
    for match in re.finditer(
        r"((?:[A-Z][A-Za-z&.\-'\s]{1,50}\s)?(?:University|College|Institute|School|Academy)[^.;]{0,140})",
        cleaned,
    ):
        chunk = _clean_line(match.group(1))
        if len(chunk) < 8:
            continue
        date_match = DATE_TOKEN_PATTERN.search(chunk)
        records.append(
            EducationRecord(
                degree=None,
                institution=chunk,
                start_date=date_match.group(1) if date_match else None,
            )
        )
    return _dedupe_education(records)


def _dedupe_education(records: list[EducationRecord]) -> list[EducationRecord]:
    seen: set[tuple[str | None, str | None]] = set()
    out: list[EducationRecord] = []
    for record in records:
        key = (_clean_line(record.degree or "").lower() or None, _clean_line(record.institution or "").lower() or None)
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _split_title_company(header_line: str) -> tuple[str | None, str | None]:
    line = _clean_line(header_line)
    if " at " in line.lower():
        parts = re.split(r"\s+at\s+", line, flags=re.IGNORECASE, maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else None
    if " - " in line:
        parts = line.split(" - ", 1)
        return parts[0], parts[1]
    if "," in line:
        parts = line.split(",", 1)
        return parts[0], parts[1]
    return line, None


def _extract_experience_regex(sections: dict[str, str]) -> list[ExperienceRecord]:
    text = sections.get("experience", "")
    if not text:
        return []

    lines = [line for line in text.splitlines() if _clean_line(line)]
    # Strip common section header prefixes that bleed into title
    # e.g. "Experience HR Director" → "HR Director"
    _TITLE_PREFIXES = re.compile(
        r"^(experience|employment|work experience|professional experience|work history)\s*",
        flags=re.IGNORECASE,
    )
    records: list[ExperienceRecord] = []
    i = 0
    while i < len(lines):
        line = _clean_line(lines[i])
        date_match = DATE_RANGE_PATTERN.search(line)
        if not date_match:
            i += 1
            continue

        raw_header = line[: date_match.start()].strip()
        # Prefer the text before the date on the same line; fall back to previous line only if
        # it looks like a job title (short, no date pattern), otherwise leave None.
        if not raw_header and i > 0:
            prev = _clean_line(lines[i - 1])
            if prev and not DATE_RANGE_PATTERN.search(prev) and len(prev) < 80:
                raw_header = prev
        # Strip section header prefix
        header = _TITLE_PREFIXES.sub("", raw_header).strip() or None
        title, company = _split_title_company(header) if header else (None, None)

        description_parts: list[str] = []
        j = i + 1
        while j < len(lines):
            candidate = _clean_line(lines[j])
            if DATE_RANGE_PATTERN.search(candidate):
                break
            description_parts.append(candidate)
            j += 1

        records.append(
            ExperienceRecord(
                title=title,
                company=company,
                start_date=date_match.group("start"),
                end_date=date_match.group("end"),
                description=" ".join(description_parts) if description_parts else None,
            )
        )
        i = j
    return records


def _extract_experience_global(text: str) -> list[ExperienceRecord]:
    cleaned = re.sub(r"\s+", " ", text)
    records: list[ExperienceRecord] = []
    for match in DATE_RANGE_PATTERN.finditer(cleaned):
        left_ctx = cleaned[max(0, match.start() - 140) : match.start()].strip()
        right_ctx = cleaned[match.end() : min(len(cleaned), match.end() + 220)].strip()
        header = left_ctx.split(".")[-1].strip()
        title, company = _split_title_company(header)
        records.append(
            ExperienceRecord(
                title=title,
                company=company,
                start_date=match.group("start"),
                end_date=match.group("end"),
                description=right_ctx[:200] if right_ctx else None,
            )
        )
    if records:
        return _dedupe_experience(records)

    # Fallback: support single-date experience entries commonly found in Sneha profiles
    # (e.g. "01/2017 VR Designer Company Name ...").
    for match in re.finditer(
        rf"(?P<start>{DATE_TOKEN})\s+(?P<title>[A-Za-z][A-Za-z0-9/&().,'\- ]{{2,80}}?)(?=\s+(?:Company Name|City|State|Education|Skills|Highlights|$))",
        cleaned,
        flags=re.IGNORECASE,
    ):
        title = _clean_line(match.group("title"))
        if not title:
            continue
        records.append(
            ExperienceRecord(
                title=title,
                company=None,
                start_date=match.group("start"),
                end_date=None,
                description=None,
            )
        )

    for match in re.finditer(
        rf"(?P<title>[A-Za-z][A-Za-z0-9/&().,'\- ]{{2,80}}?)\s*,?\s*(?P<start>{DATE_TOKEN})(?!\s*(?:to|-|–|—|－))",
        cleaned,
        flags=re.IGNORECASE,
    ):
        title = _clean_line(match.group("title"))
        if not title or title.lower().endswith(("education", "skills", "summary", "highlights")):
            continue
        records.append(
            ExperienceRecord(
                title=title,
                company=None,
                start_date=match.group("start"),
                end_date=None,
                description=None,
            )
        )
    return _dedupe_experience(records)


def _dedupe_experience(records: list[ExperienceRecord]) -> list[ExperienceRecord]:
    seen: set[tuple[str | None, str | None, str | None, str | None]] = set()
    out: list[ExperienceRecord] = []
    for record in records:
        key = (
            _clean_line(record.title or "").lower() or None,
            _clean_line(record.company or "").lower() or None,
            _clean_line(record.start_date or "").lower() or None,
            _clean_line(record.end_date or "").lower() or None,
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(record)
    return out


def _to_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    token = value.strip().lower()
    if token in {"present", "current", "now"}:
        return datetime.utcnow()
    for fmt in ("%Y-%m", "%Y/%m", "%Y"):
        try:
            return datetime.strptime(token, fmt)
        except ValueError:
            continue
    return None


def build_career_trajectory(experience: list[ExperienceRecord]) -> dict:
    if not experience:
        return {"has_trajectory": False, "progression": "insufficient-data", "moves": []}

    timeline: list[dict] = []
    for item in experience:
        timeline.append(
            {
                "title": _clean_line(item.title or "") or None,
                "company": _clean_line(item.company or "") or None,
                "start_date": item.start_date,
                "end_date": item.end_date,
                "start_dt": _to_datetime(item.start_date),
            }
        )
    timeline.sort(key=lambda row: row.get("start_dt") or datetime.min)
    moves: list[dict] = []
    for idx, row in enumerate(timeline):
        if idx == 0:
            continue
        prev = timeline[idx - 1]
        if row.get("title") == prev.get("title") and row.get("company") == prev.get("company"):
            continue
        moves.append(
            {
                "from_title": prev.get("title"),
                "to_title": row.get("title"),
                "from_company": prev.get("company"),
                "to_company": row.get("company"),
                "at": row.get("start_date"),
            }
        )

    progression = "stable"
    if len(moves) >= 2:
        progression = "growth"
    if moves and any(move.get("from_company") != move.get("to_company") for move in moves):
        progression = "transition"

    return {
        "has_trajectory": True,
        "progression": progression,
        "first_role": {
            "title": timeline[0].get("title"),
            "company": timeline[0].get("company"),
            "start_date": timeline[0].get("start_date"),
        },
        "latest_role": {
            "title": timeline[-1].get("title"),
            "company": timeline[-1].get("company"),
            "start_date": timeline[-1].get("start_date"),
            "end_date": timeline[-1].get("end_date"),
        },
        "moves": moves[:6],
    }


def _extract_with_spacy(text: str) -> dict:
    global _SPACY_NLP, _SPACY_LOAD_ATTEMPTED, _SPACY_RUNTIME_DISABLED
    if _SPACY_RUNTIME_DISABLED:
        return {}
    if not _SPACY_LOAD_ATTEMPTED:
        try:
            import spacy  # type: ignore
        except Exception:
            _SPACY_NLP = None
            _SPACY_LOAD_ATTEMPTED = True
            return {}

        nlp = None
        for model_name in ("en_core_web_sm", "en_core_web_md"):
            try:
                nlp = spacy.load(model_name, disable=["lemmatizer", "textcat"])
                break
            except Exception:
                continue
        _SPACY_NLP = nlp
        _SPACY_LOAD_ATTEMPTED = True
        if _SPACY_NLP is not None:
            logger.info("spaCy model initialized")

    if _SPACY_NLP is None:
        return {}

    try:
        doc = _SPACY_NLP(text[:SPACY_CHAR_LIMIT])
    except Exception as exc:
        _SPACY_RUNTIME_DISABLED = True
        logger.warning("spaCy disabled for this run after extraction failure: %s", exc)
        return {}
    orgs = _dedupe_preserve([ent.text for ent in doc.ents if ent.label_ == "ORG"])
    people = _dedupe_preserve([ent.text for ent in doc.ents if ent.label_ == "PERSON"])
    dates = _dedupe_preserve([ent.text for ent in doc.ents if ent.label_ == "DATE"])
    return {"orgs": orgs, "people": people, "dates": dates}


def _merge_extractions(
    base: ResumeExtraction,
    *,
    spacy_data: dict,
) -> ResumeExtraction:
    if spacy_data:
        if not base.name and spacy_data.get("people"):
            base.name = spacy_data["people"][0]
        # NOTE: We intentionally do NOT synthesize experience records from spaCy ORG/DATE
        # entities because ORG often captures tech names (Python, TensorFlow) rather than
        # company names, producing noisy data. If experience is still empty after all
        # parsing modes, the RAG pipeline supplies raw.resume_text as context to the Agent.
    return base


def _needs_programmatic_enrichment(extraction: ResumeExtraction) -> bool:
    """Return True if the rule-based extraction is insufficient and programmatic parsers should run.

    Decisions:
    - contact info (email/phone) alone is not enough — we still want skills & experience.
    - missing name without any contact is a strong signal of poor parsing.
    """
    missing_skills = len(extraction.skills) == 0
    missing_experience = len(extraction.experience) == 0
    missing_education = len(extraction.education) == 0

    # If all three core structured fields are empty, always enrich.
    if missing_skills and missing_experience and missing_education:
        return True

    # Skills are the most important field for matching — enrich if missing even if other fields exist.
    if missing_skills:
        return True

    # Experience empty AND education empty → weak profile, worth enriching.
    if missing_experience and missing_education:
        return True

    # If we also don't know who this person is, enrich.
    if extraction.name is None and not (extraction.email or extraction.phone):
        return True

    return False


def parse_resume_text(text: str, *, parser_mode: str = "hybrid") -> ResumeExtraction:
    sections = split_sections(text)
    email, phone = _extract_contacts(text)
    summary = sections.get("summary")
    if not summary:
        summary = _clean_line(text[:280]) if text else None

    extraction = ResumeExtraction(
        summary=summary,
        name=_extract_name(text, sections),
        email=email,
        phone=phone,
        skills=_extract_skills_regex(sections, text),
        education=_extract_education_regex(sections),
        experience=_extract_experience_regex(sections),
        sections=sections,
    )

    if not extraction.education:
        extraction.education = _extract_education_global(text)
    if not extraction.experience:
        extraction.experience = _extract_experience_global(text)
    extraction.career_trajectory = build_career_trajectory(extraction.experience)

    if parser_mode == "rule":
        return extraction

    if parser_mode == "spacy":
        spacy_data = _extract_with_spacy(text)
        return _merge_extractions(extraction, spacy_data=spacy_data)

    if parser_mode == "hybrid":
        if not _needs_programmatic_enrichment(extraction):
            return extraction
        # Enrich only when rule-based extraction is weak.
        spacy_data = _extract_with_spacy(text)
        extraction = _merge_extractions(extraction, spacy_data=spacy_data)
        return extraction

    return extraction


def extract_text_from_pdf(path: Path) -> str:
    """
    Extract text from PDF using pdfplumber first, then pdfminer.six fallback.
    """
    try:
        import pdfplumber  # type: ignore

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                if page_text.strip():
                    pages.append(page_text)
        text = "\n".join(pages).strip()
        if text:
            return text
    except Exception as exc:
        logger.warning("pdfplumber extraction failed: %s", exc)

    try:
        from pdfminer.high_level import extract_text  # type: ignore

        return (extract_text(str(path)) or "").strip()
    except Exception as exc:
        logger.warning("pdfminer extraction failed: %s", exc)
        return ""
