#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pymongo import MongoClient
import os


SKILL_FIELDS = ("skills", "normalized_skills", "abilities")
ALLOWED_SHORT_TOKENS = {"c", "c++", "c#", "r", "go", "ai", "ml", "ui", "ux", "qa"}
ROLE_LIKE_EXCEPTIONS = {"sql developer"}
TECH_HINT_KEYWORDS = {
    "sql",
    "oracle",
    "mysql",
    "postgres",
    "mongodb",
    "mongo",
    "redis",
    "database",
    "python",
    "java",
    "javascript",
    "typescript",
    "node",
    "react",
    "angular",
    "vue",
    "html",
    "css",
    "aws",
    "azure",
    "gcp",
    "docker",
    "kubernetes",
    "linux",
    "windows",
    "git",
    "jenkins",
    "ansible",
    "terraform",
    "spark",
    "hadoop",
    "tableau",
    "power bi",
    "etl",
    "ssis",
    "ssrs",
    "shell",
    "bash",
    "linux",
    "unix",
    "security",
    "api",
    "flask",
    "django",
    "fastapi",
    "spring",
    "excel",
    "powerpoint",
}

# Conservative soft-skill / profile-noise lexicon.
NOISE_KEYWORDS = {
    "hardworking",
    "hard working",
    "team player",
    "good communication",
    "communication skills",
    "leadership",
    "self motivated",
    "motivated",
    "dedicated",
    "punctual",
    "honest",
    "ability to work",
    "positive attitude",
    "quick learner",
    "responsible",
    "adaptable",
    "detail oriented",
}

REVIEW_KEYWORDS = {
    "honor roll",
    "dean",
    "president",
    "member of",
    "award",
    "certification",
    "volunteer",
    "hobbies",
}

STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "in",
    "with",
    "for",
    "on",
    "as",
    "at",
    "by",
    "from",
    "under",
    "over",
    "through",
}


DOMAIN_PARENTS: dict[str, list[str]] = {
    "language": ["programming"],
    "framework": ["backend"],
    "frontend_framework": ["frontend"],
    "database": ["database"],
    "cloud": ["cloud"],
    "devops": ["devops"],
    "data": ["data"],
    "ml_ai": ["ai_ml"],
    "testing": ["testing"],
    "tool": ["tools"],
    "os_platform": ["platform"],
    "security": ["security"],
}

CANONICAL_FORM_BY_SIGNATURE = {
    "nodejs": "nodejs",
    "mongodb": "mongodb",
    "sqlserver": "sql server",
    "plsql": "pl/sql",
    "tsql": "t-sql",
    "mssql": "mssql",
    "javascript": "javascript",
}


EXACT_TAXONOMY: dict[str, tuple[str, str, list[str]]] = {
    "python": ("language", "backend", ["programming", "backend"]),
    "java": ("language", "backend", ["programming", "backend"]),
    "javascript": ("language", "backend_frontend", ["programming", "backend", "frontend"]),
    "typescript": ("language", "backend_frontend", ["programming", "backend", "frontend"]),
    "c": ("language", "systems", ["programming", "systems"]),
    "c++": ("language", "systems", ["programming", "systems"]),
    "c#": ("language", "backend", ["programming", "backend"]),
    "go": ("language", "backend", ["programming", "backend"]),
    "ruby": ("language", "backend", ["programming", "backend"]),
    "php": ("language", "backend", ["programming", "backend"]),
    "r": ("language", "data", ["programming", "data"]),
    "sql": ("language", "database", ["programming", "database"]),
    "pl/sql": ("language", "database", ["programming", "database", "sql"]),
    "t-sql": ("language", "database", ["programming", "database", "sql"]),
    "react": ("frontend_framework", "frontend", ["frontend"]),
    "angular": ("frontend_framework", "frontend", ["frontend"]),
    "vue": ("frontend_framework", "frontend", ["frontend"]),
    "next.js": ("frontend_framework", "frontend", ["frontend", "react"]),
    "nodejs": ("framework", "backend_runtime", ["backend"]),
    "express": ("framework", "backend_api", ["backend", "nodejs"]),
    "django": ("framework", "backend_api", ["backend", "python"]),
    "flask": ("framework", "backend_api", ["backend", "python"]),
    "fastapi": ("framework", "backend_api", ["backend", "python"]),
    "spring": ("framework", "backend_api", ["backend", "java"]),
    "spring boot": ("framework", "backend_api", ["backend", "java", "spring"]),
    "postgresql": ("database", "relational", ["database", "sql"]),
    "mysql": ("database", "relational", ["database", "sql"]),
    "mssql": ("database", "relational", ["database", "sql"]),
    "sql server": ("database", "relational", ["database", "sql"]),
    "oracle": ("database", "relational", ["database", "sql"]),
    "mongodb": ("database", "nosql", ["database", "nosql"]),
    "redis": ("database", "nosql", ["database", "nosql"]),
    "elasticsearch": ("database", "search", ["database", "search"]),
    "aws": ("cloud", "public_cloud", ["cloud"]),
    "azure": ("cloud", "public_cloud", ["cloud"]),
    "gcp": ("cloud", "public_cloud", ["cloud"]),
    "docker": ("devops", "container", ["devops", "containerization"]),
    "kubernetes": ("devops", "orchestration", ["devops", "containerization"]),
    "terraform": ("devops", "iac", ["devops", "cloud"]),
    "ansible": ("devops", "configuration", ["devops"]),
    "jenkins": ("devops", "ci_cd", ["devops", "ci_cd"]),
    "git": ("tool", "version_control", ["tools", "version_control"]),
    "github": ("tool", "version_control", ["tools", "version_control"]),
    "gitlab": ("tool", "version_control", ["tools", "version_control"]),
    "powerpoint": ("tool", "office_suite", ["tools"]),
    "excel": ("data", "analytics", ["data"]),
    "microsoft excel": ("data", "analytics", ["data"]),
    "pandas": ("data", "analysis", ["data", "python"]),
    "numpy": ("data", "analysis", ["data", "python"]),
    "spark": ("data", "processing", ["data", "big_data"]),
    "hadoop": ("data", "big_data", ["data", "big_data"]),
    "tableau": ("data", "bi", ["data", "bi"]),
    "power bi": ("data", "bi", ["data", "bi"]),
    "tensorflow": ("ml_ai", "deep_learning", ["ai_ml", "python"]),
    "pytorch": ("ml_ai", "deep_learning", ["ai_ml", "python"]),
    "scikit-learn": ("ml_ai", "machine_learning", ["ai_ml", "python"]),
    "linux": ("os_platform", "os", ["platform"]),
    "windows": ("os_platform", "os", ["platform"]),
    "pytest": ("testing", "test_framework", ["testing", "python"]),
    "junit": ("testing", "test_framework", ["testing", "java"]),
    "selenium": ("testing", "automation", ["testing"]),
    "postman": ("testing", "api_testing", ["testing", "backend"]),
    "etl": ("data", "data_integration", ["data"]),
    "ssis": ("data", "data_integration", ["data", "sql server"]),
    "ssrs": ("data", "reporting", ["data", "sql server"]),
    "shell scripting": ("devops", "scripting", ["devops", "platform"]),
    "powershell": ("devops", "scripting", ["devops", "platform"]),
    "sql loader": ("database", "database_tooling", ["database", "sql"]),
    "sql profiler": ("database", "database_tooling", ["database", "sql"]),
    "sql developer": ("database", "database_tooling", ["database", "sql"]),
    "rman": ("database", "database_tooling", ["database", "oracle"]),
    "awr": ("database", "database_tooling", ["database", "oracle"]),
    "toad": ("database", "database_tooling", ["database"]),
    "oem": ("database", "database_tooling", ["database", "oracle"]),
    "rac": ("database", "high_availability", ["database", "oracle"]),
    "data guard": ("database", "high_availability", ["database", "oracle"]),
    "golden gate": ("database", "replication", ["database", "oracle"]),
}


@dataclass
class AliasGroup:
    canonical: str
    aliases: list[str]
    total_frequency: int
    confidence: str


def normalize_token(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip().lower()
    token = re.sub(r"\s+", " ", token)
    token = token.strip(" ,;:/|")
    return token


def alias_signature(token: str) -> str:
    token = token.replace("&", "and")
    token = token.replace("+", " plus ")
    token = token.replace("#", " sharp ")
    token = re.sub(r"[^a-z0-9]", "", token)
    return token


def notation_signature(token: str) -> str:
    token = token.replace("&", "and")
    token = token.replace("+", " plus ")
    token = token.replace("#", " sharp ")
    token = re.sub(r"[._/\-\s]+", "", token)
    token = re.sub(r"[^a-z0-9]", "", token)
    return token


def choose_canonical(forms: Counter[str], signature: str) -> str:
    preferred = CANONICAL_FORM_BY_SIGNATURE.get(signature)
    if preferred and preferred in forms:
        return preferred

    # Keep canonical deterministic and readable.
    def score(form: str) -> tuple[int, int, int, int, str]:
        freq = forms[form]
        punctuation_penalty = 0 if re.search(r"[._/\-]", form) is None else -1
        parentheses_penalty = 0 if "(" not in form and ")" not in form else -1
        length_bonus = -len(form)
        return (freq, punctuation_penalty, parentheses_penalty, length_bonus, form)

    return max(forms.keys(), key=score)


def noise_reasons(token: str) -> list[str]:
    reasons: list[str] = []
    if token in NOISE_KEYWORDS:
        reasons.append("soft_skill_phrase")
    if any(kw in token for kw in NOISE_KEYWORDS):
        reasons.append("contains_soft_skill_keyword")
    if any(kw in token for kw in REVIEW_KEYWORDS):
        reasons.append("profile_or_award_phrase")
    if re.search(r"\b\d{4}\b", token):
        reasons.append("contains_year")
    words = token.split()
    if len(words) >= 6:
        reasons.append("very_long_phrase")
    stopword_count = sum(1 for w in words if w in STOPWORDS)
    if words and (stopword_count / len(words)) >= 0.45 and len(words) >= 4:
        reasons.append("stopword_heavy_phrase")
    if token.endswith(" skills") or token.startswith("skills "):
        reasons.append("meta_skill_label")
    return sorted(set(reasons))


def is_alias_confident(forms: list[str]) -> bool:
    if len(forms) < 2:
        return False
    notation = {notation_signature(f) for f in forms}
    if len(notation) != 1:
        return False
    if any(len(f) > 40 for f in forms):
        return False
    # Do not auto-group very short one-letter symbols unless explicitly allowed.
    if any(len(f) <= 1 for f in forms):
        return False
    return True


def is_clean_skill_phrase(token: str) -> bool:
    if not token:
        return False
    if len(token) > 35:
        return False
    words = token.split()
    if len(words) > 4:
        return False
    if re.search(r"\b(19|20)\d{2}\b", token):
        return False
    if any(noisy in token for noisy in ("company name", "city", "state", "resume profile", "summary", "experience")):
        return False
    if re.search(r"[^a-z0-9 .#+\-/]", token):
        return False
    if not re.search(r"[a-z]", token):
        return False
    return True


def is_tech_leaning_token(token: str) -> bool:
    if token in EXACT_TAXONOMY:
        return True
    return any(hint in token for hint in TECH_HINT_KEYWORDS)


def is_ontology_candidate(token: str, freq: int) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if freq < 3:
        reasons.append("low_frequency")
    if not re.search(r"[a-z]", token):
        reasons.append("non_alpha_token")
    if len(token) <= 1:
        reasons.append("too_short")
    if len(token.split()) >= 7:
        reasons.append("too_long")
    if token not in ALLOWED_SHORT_TOKENS and len(token) <= 2 and token.isalpha():
        reasons.append("short_ambiguous_token")
    if token not in ROLE_LIKE_EXCEPTIONS and re.search(
        r"\b(administrator|engineer|manager|developer|analyst|consultant|intern|director|officer)\b",
        token,
    ):
        reasons.append("role_like_token")
    nr = noise_reasons(token)
    if nr:
        reasons.extend(nr)
    return (len(reasons) == 0, sorted(set(reasons)))


def classify_taxonomy(skill: str) -> tuple[str, str, list[str]] | None:
    if skill in EXACT_TAXONOMY:
        return EXACT_TAXONOMY[skill]

    if skill.startswith("aws "):
        return ("cloud", "aws_service", ["aws", "cloud"])
    if skill.startswith("azure "):
        return ("cloud", "azure_service", ["azure", "cloud"])
    if skill.startswith("gcp "):
        return ("cloud", "gcp_service", ["gcp", "cloud"])
    if skill.startswith("oracle "):
        return ("database", "oracle", ["oracle", "database", "sql"])
    if skill.startswith("sql server ") or skill.startswith("microsoft sql server"):
        return ("database", "sql_server", ["sql server", "database", "sql"])
    if skill.startswith("database "):
        return ("database", "database_ops", ["database", "sql"])
    if skill.startswith("unix "):
        return ("os_platform", "os", ["unix", "platform"])

    if any(key in skill for key in ("python", "java", "javascript", "typescript", "golang", "ruby", "php")):
        return ("language", "backend", ["programming", "backend"])
    if any(key in skill for key in ("react", "angular", "vue", "frontend", "html", "css")):
        return ("frontend_framework", "frontend", ["frontend"])
    if any(key in skill for key in ("flask", "django", "fastapi", "spring", "express")):
        return ("framework", "backend_api", ["backend"])
    if any(key in skill for key in ("postgres", "mysql", "oracle", "sql server", "mssql", "database")):
        return ("database", "relational", ["database", "sql"])
    if any(key in skill for key in ("mongodb", "redis", "cassandra", "dynamodb")):
        return ("database", "nosql", ["database", "nosql"])
    if any(key in skill for key in ("aws", "azure", "gcp", "cloud")):
        return ("cloud", "public_cloud", ["cloud"])
    if any(key in skill for key in ("docker", "kubernetes", "terraform", "ansible", "jenkins", "ci/cd", "devops")):
        return ("devops", "infra", ["devops"])
    if any(key in skill for key in ("pandas", "numpy", "spark", "hadoop", "tableau", "power bi", "excel")):
        return ("data", "analytics", ["data"])
    if any(key in skill for key in ("tensorflow", "pytorch", "scikit", "machine learning", "deep learning", "nlp", "llm")):
        return ("ml_ai", "machine_learning", ["ai_ml"])
    if any(key in skill for key in ("pytest", "junit", "selenium", "cypress", "postman", "testing", "qa")):
        return ("testing", "qa", ["testing"])
    if any(key in skill for key in ("linux", "windows", "unix")):
        return ("os_platform", "os", ["platform"])
    if any(key in skill for key in ("git", "github", "gitlab", "jira", "confluence")):
        return ("tool", "engineering_tool", ["tools"])
    if any(key in skill for key in ("security", "oauth", "jwt", "iam", "siem", "soc")):
        return ("security", "application_security", ["security"])

    return None


def yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f"\"{escaped}\""


def dump_alias_yaml(path: Path, aliases: dict[str, list[str]]) -> None:
    lines: list[str] = []
    for canonical in sorted(aliases.keys()):
        lines.append(f"{yaml_scalar(canonical)}:")
        lines.append("  aliases:")
        for alias in aliases[canonical]:
            lines.append(f"    - {yaml_scalar(alias)}")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def dump_taxonomy_yaml(path: Path, taxonomy: dict[str, dict[str, Any]]) -> None:
    lines: list[str] = []
    for skill in sorted(taxonomy.keys()):
        item = taxonomy[skill]
        lines.append(f"{yaml_scalar(skill)}:")
        lines.append(f"  domain: {yaml_scalar(item['domain'])}")
        lines.append(f"  family: {yaml_scalar(item['family'])}")
        lines.append("  parents:")
        for parent in item["parents"]:
            lines.append(f"    - {yaml_scalar(parent)}")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def dump_review_yaml(
    path: Path,
    ambiguous_skills: list[tuple[str, int, list[str]]],
    uncertain_aliases: list[tuple[str, list[str], int]],
    taxonomy_review: list[tuple[str, int]],
) -> None:
    lines: list[str] = []
    lines.append("ambiguous_skills:")
    for token, freq, reasons in ambiguous_skills:
        lines.append(f"  - token: {yaml_scalar(token)}")
        lines.append(f"    frequency: {freq}")
        lines.append("    reasons:")
        for reason in reasons:
            lines.append(f"      - {yaml_scalar(reason)}")

    lines.append("uncertain_alias_groups:")
    for signature, forms, total_freq in uncertain_aliases:
        lines.append(f"  - signature: {yaml_scalar(signature)}")
        lines.append(f"    total_frequency: {total_freq}")
        lines.append("    forms:")
        for form in forms:
            lines.append(f"      - {yaml_scalar(form)}")

    lines.append("taxonomy_review_required:")
    for token, freq in taxonomy_review:
        lines.append(f"  - token: {yaml_scalar(token)}")
        lines.append(f"    frequency: {freq}")

    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def format_top(counter: Counter[str], limit: int) -> list[tuple[str, int]]:
    return sorted(counter.items(), key=lambda x: (-x[1], x[0]))[:limit]


def render_markdown_report(
    path: Path,
    total_docs: int,
    source_docs: Counter[str],
    field_stats: dict[str, int],
    top_overall: list[tuple[str, int]],
    top_by_source: dict[str, list[tuple[str, int]]],
    top_titles: list[tuple[str, int]],
    top_categories: list[tuple[str, int]],
    alias_groups: list[AliasGroup],
    noise_candidates: list[tuple[str, int, list[str]]],
    review_items: list[tuple[str, int, list[str]]],
    taxonomy_items: list[tuple[str, str, str, list[str], int]],
) -> None:
    lines: list[str] = []
    lines.append("# Skill Ontology Analysis")
    lines.append("")
    lines.append("Date: 2026-03-13")
    lines.append("")
    lines.append("## Dataset Snapshot")
    lines.append("")
    lines.append(f"- Total candidates analyzed: **{total_docs}**")
    lines.append("- Fields analyzed: `parsed.skills`, `parsed.normalized_skills`, `parsed.abilities`, `parsed.experience_items.title`, `category`, `source_dataset`")
    lines.append("")
    lines.append("### Source Dataset Distribution")
    lines.append("")
    for source, count in sorted(source_docs.items(), key=lambda x: (-x[1], x[0])):
        lines.append(f"- `{source}`: {count}")
    lines.append("")
    lines.append("### Skill Field Coverage (doc-level)")
    lines.append("")
    lines.append("| Field | Docs with value | Coverage |")
    lines.append("| --- | ---: | ---: |")
    for field_name, count in field_stats.items():
        pct = (count / total_docs * 100.0) if total_docs else 0.0
        lines.append(f"| `{field_name}` | {count} | {pct:.1f}% |")
    lines.append("")
    lines.append("## Skill Token Frequency (Top)")
    lines.append("")
    lines.append("| Rank | Token | Frequency |")
    lines.append("| ---: | --- | ---: |")
    for idx, (token, freq) in enumerate(top_overall, start=1):
        lines.append(f"| {idx} | `{token}` | {freq} |")
    lines.append("")
    lines.append("## Source Dataset Differences")
    lines.append("")
    for source in sorted(top_by_source.keys()):
        lines.append(f"### `{source}` Top Tokens")
        lines.append("")
        lines.append("| Rank | Token | Frequency |")
        lines.append("| ---: | --- | ---: |")
        for idx, (token, freq) in enumerate(top_by_source[source], start=1):
            lines.append(f"| {idx} | `{token}` | {freq} |")
        lines.append("")
    lines.append("## Experience Title Signals (Top)")
    lines.append("")
    lines.append("| Rank | Title | Frequency |")
    lines.append("| ---: | --- | ---: |")
    for idx, (title, freq) in enumerate(top_titles, start=1):
        lines.append(f"| {idx} | `{title}` | {freq} |")
    lines.append("")
    lines.append("## Category Signals (Top)")
    lines.append("")
    lines.append("| Rank | Category | Frequency |")
    lines.append("| ---: | --- | ---: |")
    for idx, (cat, freq) in enumerate(top_categories, start=1):
        lines.append(f"| {idx} | `{cat}` | {freq} |")
    lines.append("")
    lines.append("## Alias Candidate Groups")
    lines.append("")
    if alias_groups:
        for group in alias_groups:
            lines.append(f"- `{group.canonical}` <= {', '.join(f'`{a}`' for a in group.aliases)} (freq={group.total_frequency}, confidence={group.confidence})")
    else:
        lines.append("- No high-confidence alias groups detected.")
    lines.append("")
    lines.append("## Noise Candidates")
    lines.append("")
    if noise_candidates:
        for token, freq, reasons in noise_candidates:
            lines.append(f"- `{token}` (freq={freq}) reasons: {', '.join(reasons)}")
    else:
        lines.append("- No clear noise candidates detected by conservative rules.")
    lines.append("")
    lines.append("## Review Required")
    lines.append("")
    if review_items:
        for token, freq, reasons in review_items:
            lines.append(f"- `{token}` (freq={freq}) reasons: {', '.join(reasons)}")
    else:
        lines.append("- No review-required skill tokens detected.")
    lines.append("")
    lines.append("## Taxonomy Proposal Summary")
    lines.append("")
    lines.append("| Skill | Domain | Family | Parents | Frequency |")
    lines.append("| --- | --- | --- | --- | ---: |")
    for skill, domain, family, parents, freq in taxonomy_items:
        parent_str = ", ".join(parents)
        lines.append(f"| `{skill}` | `{domain}` | `{family}` | `{parent_str}` | {freq} |")
    lines.append("")
    lines.append("## Ontology Generation Notes")
    lines.append("")
    lines.append("- Alias normalization only groups notation variants with same normalized notation signature.")
    lines.append("- Semantic alternatives are not merged as aliases.")
    lines.append("- Parent-child hierarchy is stored separately from alias mapping.")
    lines.append("- Ambiguous or low-confidence items are intentionally sent to `review_required`.")
    path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze MongoDB candidate skills and generate ontology draft files.")
    parser.add_argument("--mongo-uri", default=None, help="Override MONGODB_URI")
    parser.add_argument("--mongo-db", default=None, help="Override MONGODB_DB")
    parser.add_argument("--top-n", type=int, default=120, help="Top tokens to include in the main frequency table")
    parser.add_argument("--source-top-n", type=int, default=40, help="Top tokens per source in report")
    parser.add_argument("--output-report", default="docs/skill_ontology_analysis.md")
    parser.add_argument("--output-aliases", default="config/skill_aliases.yml")
    parser.add_argument("--output-taxonomy", default="config/skill_taxonomy.yml")
    parser.add_argument("--output-review", default="config/skill_review_required.yml")
    parser.add_argument("--min-alias-form-frequency", type=int, default=8)
    parser.add_argument("--min-alias-total-frequency", type=int, default=20)
    parser.add_argument("--min-taxonomy-frequency", type=int, default=30)
    parser.add_argument("--min-review-frequency", type=int, default=20)
    args = parser.parse_args()

    load_dotenv()
    mongo_uri = args.mongo_uri or os.getenv("MONGODB_URI")
    mongo_db = args.mongo_db or os.getenv("MONGODB_DB", "resume_matching")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI is not set. Set it in environment or .env.")

    client = MongoClient(mongo_uri)
    collection = client[mongo_db]["candidates"]

    projection = {
        "source_dataset": 1,
        "category": 1,
        "parsed.skills": 1,
        "parsed.normalized_skills": 1,
        "parsed.abilities": 1,
        "parsed.experience_items.title": 1,
    }

    total_docs = 0
    source_docs: Counter[str] = Counter()
    field_stats = {f"parsed.{field}": 0 for field in SKILL_FIELDS}
    field_stats["parsed.experience_items.title"] = 0
    field_stats["category"] = 0

    skill_counter: Counter[str] = Counter()
    source_skill_counter: dict[str, Counter[str]] = defaultdict(Counter)
    title_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()

    signature_forms: dict[str, Counter[str]] = defaultdict(Counter)

    cursor = collection.find({}, projection=projection, no_cursor_timeout=True)
    try:
        for doc in cursor:
            total_docs += 1
            source = normalize_token(doc.get("source_dataset")) or "unknown"
            source_docs[source] += 1

            category = normalize_token(doc.get("category"))
            if category:
                field_stats["category"] += 1
                category_counter[category] += 1

            parsed = doc.get("parsed") or {}

            for field in SKILL_FIELDS:
                raw_values = parsed.get(field) or []
                valid_values: list[str] = []
                if isinstance(raw_values, list):
                    for value in raw_values:
                        token = normalize_token(value)
                        if token:
                            valid_values.append(token)
                            skill_counter[token] += 1
                            source_skill_counter[source][token] += 1
                            signature_forms[alias_signature(token)][token] += 1
                if valid_values:
                    field_stats[f"parsed.{field}"] += 1

            exp_items = parsed.get("experience_items") or []
            has_title = False
            if isinstance(exp_items, list):
                for item in exp_items:
                    if not isinstance(item, dict):
                        continue
                    title = normalize_token(item.get("title"))
                    if title:
                        has_title = True
                        title_counter[title] += 1
            if has_title:
                field_stats["parsed.experience_items.title"] += 1
    finally:
        cursor.close()
        client.close()

    # 1) Alias detection (conservative)
    alias_groups: list[AliasGroup] = []
    uncertain_aliases: list[tuple[str, list[str], int]] = []
    alias_resolution: dict[str, str] = {}

    signature_rank = sorted(
        signature_forms.items(),
        key=lambda x: (-sum(x[1].values()), x[0]),
    )
    for signature, forms_counter in signature_rank:
        filtered_counter = Counter(
            {
                form: freq
                for form, freq in forms_counter.items()
                if freq >= args.min_alias_form_frequency
                and is_clean_skill_phrase(form)
                and is_tech_leaning_token(form)
            }
        )
        forms = sorted(filtered_counter.keys())
        if len(forms) < 2:
            continue
        total_freq = sum(filtered_counter.values())
        if total_freq < args.min_alias_total_frequency:
            continue
        if is_alias_confident(forms):
            canonical = choose_canonical(filtered_counter, signature)
            aliases = [form for form in forms if form != canonical]
            if aliases:
                alias_groups.append(
                    AliasGroup(
                        canonical=canonical,
                        aliases=aliases,
                        total_frequency=total_freq,
                        confidence="high",
                    )
                )
                alias_resolution[canonical] = canonical
                for alias in aliases:
                    alias_resolution[alias] = canonical
        else:
            uncertain_aliases.append((signature, forms, total_freq))

    # 2) Apply alias normalization to frequency space.
    canonical_counter: Counter[str] = Counter()
    canonical_source_counter: dict[str, Counter[str]] = defaultdict(Counter)
    for token, freq in skill_counter.items():
        canonical = alias_resolution.get(token, token)
        canonical_counter[canonical] += freq
    for source, counter in source_skill_counter.items():
        for token, freq in counter.items():
            canonical = alias_resolution.get(token, token)
            canonical_source_counter[source][canonical] += freq

    # 3) Noise + review-required detection.
    noise_candidates: list[tuple[str, int, list[str]]] = []
    review_required: list[tuple[str, int, list[str]]] = []

    for token, freq in sorted(canonical_counter.items(), key=lambda x: (-x[1], x[0])):
        reasons = noise_reasons(token)
        if reasons and freq >= args.min_review_frequency:
            noise_candidates.append((token, freq, reasons))

    for token, freq in sorted(canonical_counter.items(), key=lambda x: (-x[1], x[0])):
        candidate_ok, reasons = is_ontology_candidate(token, freq)
        if not candidate_ok and freq >= args.min_review_frequency:
            review_required.append((token, freq, reasons))

    # 4) Taxonomy proposal.
    taxonomy: dict[str, dict[str, Any]] = {}
    taxonomy_review_required: list[tuple[str, int]] = []
    for token, freq in sorted(canonical_counter.items(), key=lambda x: (-x[1], x[0])):
        candidate_ok, reasons = is_ontology_candidate(token, freq)
        if not candidate_ok:
            continue
        if freq < args.min_taxonomy_frequency:
            continue
        if not is_clean_skill_phrase(token):
            continue
        if not is_tech_leaning_token(token):
            continue
        cls = classify_taxonomy(token)
        if cls is None:
            if freq >= args.min_review_frequency:
                taxonomy_review_required.append((token, freq))
            continue
        domain, family, parents = cls
        taxonomy[token] = {"domain": domain, "family": family, "parents": parents}

    # 5) Build output lists.
    top_overall = format_top(canonical_counter, args.top_n)
    top_by_source = {
        source: format_top(counter, args.source_top_n)
        for source, counter in sorted(canonical_source_counter.items())
    }
    top_titles = format_top(title_counter, 30)
    top_categories = format_top(category_counter, 30)

    alias_yaml: dict[str, list[str]] = {}
    for group in sorted(alias_groups, key=lambda x: x.canonical):
        # Keep alias list deterministic.
        dedup_aliases = sorted(set(group.aliases))
        if dedup_aliases:
            alias_yaml[group.canonical] = dedup_aliases

    taxonomy_items = [
        (skill, data["domain"], data["family"], data["parents"], canonical_counter[skill])
        for skill, data in sorted(
            taxonomy.items(),
            key=lambda x: (-canonical_counter[x[0]], x[0]),
        )
    ]

    # 6) Write outputs.
    report_path = Path(args.output_report)
    aliases_path = Path(args.output_aliases)
    taxonomy_path = Path(args.output_taxonomy)
    review_path = Path(args.output_review)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    aliases_path.parent.mkdir(parents=True, exist_ok=True)
    taxonomy_path.parent.mkdir(parents=True, exist_ok=True)
    review_path.parent.mkdir(parents=True, exist_ok=True)

    render_markdown_report(
        path=report_path,
        total_docs=total_docs,
        source_docs=source_docs,
        field_stats=field_stats,
        top_overall=top_overall,
        top_by_source=top_by_source,
        top_titles=top_titles,
        top_categories=top_categories,
        alias_groups=sorted(alias_groups, key=lambda x: (-x.total_frequency, x.canonical))[:80],
        noise_candidates=noise_candidates[:120],
        review_items=review_required[:160],
        taxonomy_items=taxonomy_items[:160],
    )

    dump_alias_yaml(aliases_path, alias_yaml)
    dump_taxonomy_yaml(taxonomy_path, taxonomy)
    dump_review_yaml(
        review_path,
        ambiguous_skills=review_required[:220],
        uncertain_aliases=sorted(uncertain_aliases, key=lambda x: (-x[2], x[0]))[:120],
        taxonomy_review=taxonomy_review_required[:200],
    )

    print(f"Generated: {report_path}")
    print(f"Generated: {aliases_path}")
    print(f"Generated: {taxonomy_path}")
    print(f"Generated: {review_path}")
    print(f"Total candidates analyzed: {total_docs}")
    print(f"Unique skill tokens (canonicalized): {len(canonical_counter)}")
    print(f"Alias groups (high confidence): {len(alias_yaml)}")
    print(f"Taxonomy entries: {len(taxonomy)}")
    print(f"Review-required skills: {len(review_required)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
