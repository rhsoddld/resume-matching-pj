from __future__ import annotations

from datetime import datetime
import re
from typing import Iterable, Sequence

import pandas as pd

from backend.schemas.candidate import ParsedExperienceItem


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

CATEGORY_RULES = {
    "DATABASE": ["dba", "database administrator", "oracle dba", "sql server", "database developer", "database admin", "mysql dba", "postgresql dba"],
    "BACKEND": ["backend", "java developer", "python developer", "c# developer", "c++ developer", "nodejs", "spring boot", "django", "ruby on rails", ".net developer", "golang", "php developer"],
    "FRONTEND": ["frontend", "react", "angular", "vue", "ui developer", "html", "css", "javascript developer", "web developer"],
    "DATA-ENGINEERING": ["data engineer", "hadoop", "spark", "etl", "data pipeline", "kafka", "snowflake", "big data"],
    "DATA-ANALYSIS": ["data analyst", "data scientist", "business analyst", "machine learning", "deep learning", "nlp", "computer vision", "statistics"],
    "DEVOPS": ["devops", "sre", "site reliability", "aws", "azure", "gcp", "docker", "kubernetes", "jenkins", "cicd", "terraform"],
    "QA": ["qa", "quality assurance", "tester", "test engineer", "automation testing", "manual testing", "selenium", "cypress"],
    "PROJECT-MANAGEMENT": ["scrum master", "product manager", "project manager", "agile", "pmp", "product owner"],
    "SYSTEM-ADMINISTRATION": ["system admin", "sysadmin", "linux admin", "windows admin", "network admin", "infrastructure"],
    "MOBILE": ["ios developer", "android developer", "mobile developer", "flutter", "react native", "swift", "kotlin"],
    "SECURITY": ["security", "cybersecurity", "penetration testing", "infosec", "soc analyst", "ethical hacker"],
}


def clean_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.lower() in {"nan", "none", "null", "na", "n/a"}:
        return None
    return re.sub(r"\s+", " ", text)


def normalize_identifier(value: object, prefix: str) -> str:
    if value is None:
        return f"{prefix}-unknown"
    try:
        if pd.isna(value):
            return f"{prefix}-unknown"
    except Exception:
        pass

    if isinstance(value, int) and not isinstance(value, bool):
        normalized = str(value)
    elif isinstance(value, float) and value.is_integer():
        normalized = str(int(value))
    else:
        normalized = str(value).strip()

    if not normalized:
        normalized = "unknown"
    return f"{prefix}-{normalized}"


def dedupe_preserve(items: Iterable[str]) -> list[str]:
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


def stable_sorted(values: Sequence[str]) -> list[str]:
    return sorted({value for value in values if value})


def normalize_skill(skill: str) -> str:
    token = re.sub(r"\s+", " ", skill.strip().lower())
    token = token.replace("&", " and ")
    return re.sub(r"\s+", " ", token).strip(" ,;:/|")


def normalize_skill_list(values: Iterable[object]) -> tuple[list[str], list[str]]:
    skills = [clean_text(value) for value in values]
    raw = dedupe_preserve([skill for skill in skills if skill is not None])
    normalized = dedupe_preserve([normalize_skill(skill) for skill in raw])
    return raw, normalized


def normalize_month(value: object) -> str | None:
    text = clean_text(value)
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


def month_to_datetime(value: str | None, *, default_now: bool) -> datetime | None:
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


def estimate_experience_years(items: Sequence[ParsedExperienceItem]) -> float | None:
    intervals: list[tuple[int, int]] = []
    for item in items:
        start = month_to_datetime(item.start_date, default_now=False)
        end = month_to_datetime(item.end_date, default_now=True)
        if start is None:
            continue
        if end is None:
            end = datetime.utcnow()
        start_idx = start.year * 12 + (start.month - 1)
        end_idx = end.year * 12 + (end.month - 1)
        if end_idx < start_idx:
            continue
        intervals.append((start_idx, end_idx))

    if not intervals:
        return None

    intervals.sort(key=lambda item: (item[0], item[1]))
    merged: list[list[int]] = []
    for start_idx, end_idx in intervals:
        if not merged:
            merged.append([start_idx, end_idx])
            continue
        prev_start, prev_end = merged[-1]
        if start_idx <= prev_end + 1:
            if end_idx > prev_end:
                merged[-1][1] = end_idx
        else:
            merged.append([start_idx, end_idx])

    total_months = sum((end - start + 1) for start, end in merged)
    if total_months <= 0:
        return None
    return round(total_months / 12.0, 1)


def infer_seniority_level(experience_years: float | None) -> str | None:
    if experience_years is None:
        return None
    if experience_years < 2:
        return "junior"
    if experience_years < 5:
        return "mid"
    if experience_years < 8:
        return "senior"
    return "lead"


def prepare_embedding_text(text: str, *, char_limit: int = 4000) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if not compact:
        compact = "empty resume"
    return compact[:char_limit]


def extract_sneha_skills(resume_text: str) -> tuple[list[str], list[str]]:
    match = re.search(r"\bskills\b(.*)", resume_text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return [], []
    tail = match.group(1)[:1200]
    tokens = re.split(r"[,\n;|]", tail)
    return normalize_skill_list(tokens[:60])


def build_embedding_text(
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
    char_limit: int = 4000,
) -> str:
    parts: list[str] = []
    core_set = set(core_skills)
    capability_set = set(capability_phrases)
    specialized = [
        token
        for token in canonical_skills
        if token not in core_set and token not in capability_set and len(token.split()) <= 3
    ]

    if name:
        parts.append(f"Name: {name}")
    if category:
        parts.append(f"Category: {category}")
    if summary:
        parts.append(f"Summary: {summary}")
    if core_skills:
        parts.append("Core skills: " + "; ".join(core_skills[:30]))
    if specialized:
        parts.append("Specialized skills: " + "; ".join(specialized[:20]))
    if expanded_skills:
        parts.append("Expanded skills: " + "; ".join(expanded_skills[:30]))
    if capability_phrases:
        parts.append("Capabilities: " + "; ".join(capability_phrases[:5]))
    if experience_titles:
        parts.append("Experience titles: " + "; ".join(experience_titles[:20]))
    if fallback_text and not parts:
        parts.append(fallback_text)
    return prepare_embedding_text("\n".join(parts), char_limit=char_limit)


def impute_category_rule_based(experience_titles: list[str], core_skills: list[str]) -> str:
    score_board = {category: 0 for category in CATEGORY_RULES}
    combined_text = " ".join([title for title in experience_titles if title] + [skill for skill in core_skills if skill]).lower()

    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            if re.search(r"\b" + re.escape(keyword) + r"\b", combined_text):
                score_board[category] += 1

    best_category = max(score_board, key=score_board.get)
    return best_category if score_board[best_category] > 0 else "SOFTWARE-ENGINEERING"

