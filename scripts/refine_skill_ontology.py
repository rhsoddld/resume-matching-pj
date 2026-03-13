#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pymongo import MongoClient


SKILL_FIELDS = ("skills", "normalized_skills", "abilities")

# Precision-first core skills for scoring taxonomy.
CORE_SKILL_WHITELIST = {
    "angularjs",
    "ansible",
    "awr",
    "aws",
    "aws rds",
    "azure",
    "c#",
    "c++",
    "css",
    "css3",
    "cyber security",
    "data guard",
    "data security",
    "docker",
    "etl",
    "excel",
    "git",
    "github",
    "golden gate",
    "hadoop",
    "hp-unix",
    "html",
    "html5",
    "information security",
    "java",
    "javascript",
    "jenkins",
    "linux",
    "microsoft azure",
    "microsoft excel",
    "microsoft sql server",
    "microsoft windows",
    "mongodb",
    "ms excel",
    "ms sql server",
    "mssql",
    "mysql",
    "network security",
    "nodejs",
    "oem",
    "oracle",
    "oracle asm",
    "oracle data guard",
    "oracle databases",
    "oracle exadata",
    "oracle goldengate",
    "oracle rac",
    "oracle streams",
    "php",
    "pl/sql",
    "postgres",
    "postgresql",
    "power bi",
    "powershell",
    "python",
    "rac",
    "red hat linux",
    "rman",
    "ruby",
    "security",
    "shell scripting",
    "sql",
    "sql loader",
    "sql profiler",
    "sql server",
    "sql server integration services",
    "sql server management studio",
    "sql server reporting services",
    "ssis",
    "ssrs",
    "system security",
    "t-sql",
    "tableau",
    "toad",
    "unix",
    "windows",
    "windows server",
    "database administration",
    "database management",
    "performance tuning",
    "disaster recovery",
    "backup and recovery",
    "high availability",
    "capacity planning",
    "query optimization",
    "database design",
    "database monitoring",
    "replication",
    "clustering",
    "database security",
    "data modeling",
    "db2",
    "sybase",
    "teradata",
    "informix",
    "hbase",
    "agile",
    "scrum",
    "kanban",
    "jira",
    "confluence",
    "project management",
    "sdlc",
    "itil",
    "network infrastructure",
    "networking",
    "tcp/ip",
    "active directory",
    "firewall",
    "vpn",
    "nagios",
    "splunk",
    "puppet",
    "chef",
    "jboss",
    "tomcat",
    "weblogic",
    "websphere",
    "informatica",
    "talend",
    "datastage",
    "crystal reports",
    "cognos",
    "obiee",
    "microstrategy",
    "data entry",
    "process improvement",
    "client support",
    "technical support",
    "reporting",
}

ROLE_WORDS = {
    "administrator",
    "admin",
    "engineer",
    "developer",
    "manager",
    "analyst",
    "consultant",
    "director",
    "architect",
    "officer",
    "specialist",
    "coordinator",
    "assistant",
    "dba",
}

ROLE_EXCEPTIONS = {
    "oracle enterprise manager",
    "enterprise manager",
    "oracle enterprise manager (oem)",
    "sql server management studio",
    "system security",
}

CAPABILITY_WORDS = {
    "administration",
    "backup",
    "backups",
    "cloning",
    "configuration",
    "consolidation",
    "creation",
    "deployment",
    "design",
    "development",
    "documentation",
    "encryption",
    "implementation",
    "installation",
    "integrity",
    "maintenance",
    "management",
    "migration",
    "migrations",
    "mirroring",
    "modeling",
    "monitoring",
    "object",
    "objects",
    "optimization",
    "partitioning",
    "patching",
    "performance",
    "recovery",
    "refresh",
    "refreshes",
    "refreshing",
    "replication",
    "reporting",
    "scripting",
    "security",
    "support",
    "testing",
    "troubleshooting",
    "triggers",
    "tuning",
    "upgrade",
    "upgrades",
    "upgrading",
}

VERSION_PATTERNS = [
    re.compile(r"^(sql server|ms sql server|microsoft sql server)\s+([0-9]{4}(?:\s*r2)?|[0-9]{4}r2)$"),
    re.compile(r"^(windows(?: server)?)\s+(xp|nt|7|8|10|[0-9]{4})$"),
    re.compile(r"^(oracle)\s+([0-9]+(?:\.[0-9]+)+|[0-9]{1,2}[a-z](?:r[0-9]+)?|[0-9]{1,2}[a-z]/[0-9]{1,2}[a-z])$"),
    re.compile(r"^(oracle)\s+([0-9]{1,2}[a-z]\s+rac)$"),
]

CANONICAL_MERGE_MAP = {
    "mssql": "sql server",
    "ms sql server": "sql server",
    "microsoft sql server": "sql server",
    "postgres": "postgresql",
    "ms excel": "excel",
    "microsoft excel": "excel",
    "microsoft azure": "azure",
    "microsoft windows": "windows",
    "oracle data guard": "data guard",
    "oracle goldengate": "golden gate",
    "oracle rac": "rac",
}


def normalize(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    token = value.strip().lower()
    token = re.sub(r"\s+", " ", token)
    return token.strip(" ,;:/|")


def load_yaml(path: Path) -> Any:
    if not path.exists():
        raise FileNotFoundError(f"Missing input file: {path}")
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def dump_yaml(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=False, sort_keys=False, default_flow_style=False)


def build_alias_map(alias_doc: dict[str, Any]) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for canonical, item in alias_doc.items():
        c = normalize(canonical)
        if not c:
            continue
        reverse[c] = c
        aliases = item.get("aliases", []) if isinstance(item, dict) else []
        for alias in aliases:
            a = normalize(alias)
            if a:
                reverse[a] = c
    return reverse


def collect_skill_frequencies(mongo_uri: str, mongo_db: str, alias_map: dict[str, str]) -> Counter[str]:
    client = MongoClient(mongo_uri)
    coll = client[mongo_db]["candidates"]
    counter: Counter[str] = Counter()
    projection = {f"parsed.{field}": 1 for field in SKILL_FIELDS}
    cursor = coll.find({}, projection=projection, no_cursor_timeout=True)
    try:
        for doc in cursor:
            parsed = doc.get("parsed") or {}
            for field in SKILL_FIELDS:
                values = parsed.get(field) or []
                if not isinstance(values, list):
                    continue
                for value in values:
                    token = normalize(value)
                    if not token:
                        continue
                    canonical = alias_map.get(token, token)
                    counter[canonical] += 1
    finally:
        cursor.close()
        client.close()
    return counter


def is_role_like(term: str) -> bool:
    if term in ROLE_EXCEPTIONS:
        return False
    words = term.split()
    if not words:
        return False
    # Precision: role-like when role nouns appear as standalone words.
    return any(word in ROLE_WORDS for word in words)


def parse_versioned_skill(term: str) -> tuple[str, str] | None:
    for pattern in VERSION_PATTERNS:
        m = pattern.match(term)
        if not m:
            continue
        canonical = normalize(m.group(1))
        version = normalize(m.group(2))
        canonical = canonical.replace("microsoft sql server", "sql server").replace("ms sql server", "sql server")
        return canonical, version

    # Broader but still boundary-based fallback for year suffixes.
    m2 = re.match(r"^(.+?)\s+([0-9]{4}(?:\s*r2)?)$", term)
    if m2:
        canonical = normalize(m2.group(1))
        version = normalize(m2.group(2))
        canonical = canonical.replace("microsoft sql server", "sql server").replace("ms sql server", "sql server")
        return canonical, version
    return None


def is_capability_phrase(term: str) -> bool:
    words = term.split()
    if len(words) < 2:
        return False
    # Precision: require explicit capability words, not substring contains.
    if " ".join(words[:1]) in {"database", "sql", "oracle", "unix", "windows"} and any(w in CAPABILITY_WORDS for w in words[1:]):
        return True
    if "database" in words and any(w in CAPABILITY_WORDS for w in words):
        return True
    if "sql" in words and any(w in CAPABILITY_WORDS for w in words):
        return True
    if "support" in words and ("production" in words or "customer" in words):
        return True
    if "service" in words and "customer" in words:
        return True
    return False


def classify_term(term: str) -> str:
    if parse_versioned_skill(term):
        return "versioned_skill"
    if is_role_like(term):
        return "role_like"
    if term in CORE_SKILL_WHITELIST:
        return "core_skill"
    if is_capability_phrase(term):
        return "capability_phrase"
    return "review_required"


def infer_parents(term: str) -> list[str]:
    words = set(term.split())
    parents: list[str] = []
    if "sql" in words or "pl/sql" in words or "t-sql" in words or term.startswith("sql server"):
        parents.extend(["sql", "database"])
    if "database" in words:
        if "database" not in parents:
            parents.append("database")
    if "oracle" in words:
        parents.extend(["oracle", "database"])
    if "mysql" in words or "postgresql" in words or "mongodb" in words:
        parents.append("database")
    if "aws" in words:
        parents.extend(["aws", "cloud"])
    if "azure" in words:
        parents.extend(["azure", "cloud"])
    if "linux" in words or "unix" in words or "windows" in words:
        parents.append("platform")
    if "security" in words:
        parents.append("security")
    if "etl" in words or "ssis" in words or "ssrs" in words:
        parents.append("data")
    if "tableau" in words or "power" in words and "bi" in words:
        parents.append("data")

    dedup: list[str] = []
    for p in parents:
        if p not in dedup:
            dedup.append(p)
    return dedup


def refine(
    taxonomy_path: Path,
    alias_path: Path,
    review_path: Path,
    output_taxonomy: Path,
    output_roles: Path,
    output_versions: Path,
    output_capabilities: Path,
    output_review: Path,
    output_report: Path,
    mongo_uri: str,
    mongo_db: str,
) -> None:
    taxonomy_doc = load_yaml(taxonomy_path)
    alias_doc = load_yaml(alias_path)
    review_doc = load_yaml(review_path)
    alias_map = build_alias_map(alias_doc)
    freq_counter = collect_skill_frequencies(mongo_uri, mongo_db, alias_map)

    previous_review_freq = {
        normalize(item.get("token")): int(item.get("frequency", 0))
        for item in review_doc.get("ambiguous_skills", [])
        if isinstance(item, dict) and normalize(item.get("token"))
    }

    terms = set(normalize(k) for k in taxonomy_doc.keys())
    terms.update(previous_review_freq.keys())
    terms.discard("")

    core_taxonomy: dict[str, dict[str, Any]] = {}
    role_candidates: dict[str, dict[str, Any]] = {}
    versioned: dict[str, dict[str, Any]] = {}
    capabilities: dict[str, dict[str, Any]] = {}
    refined_review: list[dict[str, Any]] = []
    canonical_merge_review: list[dict[str, Any]] = []

    moved_examples = {
        "role_like": [],
        "versioned_skill": [],
        "capability_phrase": [],
    }

    for term in sorted(terms):
        freq = int(freq_counter.get(term, 0))
        if freq == 0:
            freq = int(previous_review_freq.get(term, 0))

        if term in CANONICAL_MERGE_MAP:
            canonical_merge_review.append(
                {
                    "token": term,
                    "frequency": freq,
                    "reasons": ["canonical_merge_candidate"],
                    "suggested_canonical": CANONICAL_MERGE_MAP[term],
                }
            )
            continue

        cls = classify_term(term)
        existing_meta = taxonomy_doc.get(term)

        if cls == "core_skill" and isinstance(existing_meta, dict):
            core_taxonomy[term] = {
                "domain": existing_meta.get("domain", "unknown"),
                "family": existing_meta.get("family", "unknown"),
                "parents": existing_meta.get("parents", []),
            }
            continue

        if cls == "role_like":
            role_candidates[term] = {
                "frequency": freq,
                "suggested_parents": infer_parents(term),
                "reason": "role_like",
            }
            if len(moved_examples["role_like"]) < 10:
                moved_examples["role_like"].append(term)
            continue

        if cls == "versioned_skill":
            parsed = parse_versioned_skill(term)
            canonical, version = parsed if parsed else (term, "unknown")
            versioned[term] = {
                "canonical": canonical,
                "version": version,
                "frequency": freq,
            }
            if len(moved_examples["versioned_skill"]) < 10:
                moved_examples["versioned_skill"].append(term)
            continue

        if cls == "capability_phrase":
            capabilities[term] = {
                "frequency": freq,
                "parents": infer_parents(term),
                "reason": "capability_phrase",
            }
            if len(moved_examples["capability_phrase"]) < 10:
                moved_examples["capability_phrase"].append(term)
            continue

        reasons = []
        if term in previous_review_freq:
            reasons.append("previous_review_required")
        if not is_role_like(term) and not parse_versioned_skill(term) and not is_capability_phrase(term):
            reasons.append("not_in_core_whitelist")
        if not reasons:
            reasons.append("classification_uncertain")
        refined_review.append(
            {
                "token": term,
                "frequency": freq,
                "reasons": sorted(set(reasons)),
            }
        )

    # Keep only higher-signal role/capability/version entries.
    role_candidates = dict(
        sorted(
            ((k, v) for k, v in role_candidates.items() if int(v["frequency"]) >= 15),
            key=lambda x: (-int(x[1]["frequency"]), x[0]),
        )
    )
    versioned = dict(
        sorted(
            ((k, v) for k, v in versioned.items() if int(v["frequency"]) >= 10),
            key=lambda x: (-int(x[1]["frequency"]), x[0]),
        )
    )
    capabilities = dict(
        sorted(
            ((k, v) for k, v in capabilities.items() if int(v["frequency"]) >= 15),
            key=lambda x: (-int(x[1]["frequency"]), x[0]),
        )
    )

    # Slim core taxonomy: high-confidence skills only.
    core_taxonomy = dict(
        sorted(
            (
                (k, v)
                for k, v in core_taxonomy.items()
                if int(freq_counter.get(k, 0)) >= 20 or k in {"postgresql", "nodejs", "ansible", "docker"}
            ),
            key=lambda x: (-int(freq_counter.get(x[0], 0)), x[0]),
        )
    )

    refined_review_sorted = sorted(
        (
            item
            for item in refined_review
            if int(item.get("frequency", 0)) >= 10
        ),
        key=lambda x: (-int(x["frequency"]), x["token"]),
    )
    canonical_merge_review_sorted = sorted(
        (
            item
            for item in canonical_merge_review
            if int(item.get("frequency", 0)) >= 10
        ),
        key=lambda x: (-int(x["frequency"]), x["token"]),
    )

    # Write outputs (without touching original files).
    dump_yaml(output_taxonomy, core_taxonomy)
    dump_yaml(output_roles, role_candidates)
    dump_yaml(output_versions, versioned)
    dump_yaml(output_capabilities, capabilities)
    dump_yaml(
        output_review,
        {
            "ambiguous_skills": refined_review_sorted,
            "canonical_merge_candidates": canonical_merge_review_sorted,
            "source_note": "Generated by refine_skill_ontology.py without overwriting first-pass files.",
        },
    )

    # Report
    report_lines = []
    report_lines.append("# Skill Ontology Refinement")
    report_lines.append("")
    report_lines.append("Date: 2026-03-13")
    report_lines.append("")
    report_lines.append("## Why Refinement Was Needed")
    report_lines.append("")
    report_lines.append("- 1st-pass taxonomy included many role phrases and operational capability phrases.")
    report_lines.append("- Substring-based heuristics could misclassify non-skill phrases (example: `excellent customer service` vs `excel`).")
    report_lines.append("- Versioned product strings were mixed with canonical skills.")
    report_lines.append("")
    report_lines.append("## Refinement Rules")
    report_lines.append("")
    report_lines.append("- `core_skill`: exact whitelist + existing taxonomy metadata reuse.")
    report_lines.append("- `role_like`: boundary-based role noun detection (no broad substring scoring).")
    report_lines.append("- `versioned_skill`: strict version regex parsing into `canonical` and `version`.")
    report_lines.append("- `capability_phrase`: action/operation phrases separated from core taxonomy.")
    report_lines.append("- Ambiguous items remain in `review_required_refined` (conservative by design).")
    report_lines.append("")
    report_lines.append("## Output Summary")
    report_lines.append("")
    report_lines.append(f"- Slim core taxonomy entries: **{len(core_taxonomy)}**")
    report_lines.append(f"- Role-like candidates: **{len(role_candidates)}**")
    report_lines.append(f"- Versioned skills: **{len(versioned)}**")
    report_lines.append(f"- Capability phrases: **{len(capabilities)}**")
    report_lines.append(f"- Review-required (refined): **{len(refined_review_sorted)}**")
    report_lines.append(f"- Canonical merge candidates: **{len(canonical_merge_review_sorted)}**")
    report_lines.append("")
    report_lines.append("## Representative Moves")
    report_lines.append("")
    report_lines.append("- role_like moved examples:")
    for item in moved_examples["role_like"]:
        report_lines.append(f"  - `{item}`")
    report_lines.append("- versioned_skill moved examples:")
    for item in moved_examples["versioned_skill"]:
        report_lines.append(f"  - `{item}`")
    report_lines.append("- capability_phrase moved examples:")
    for item in moved_examples["capability_phrase"]:
        report_lines.append(f"  - `{item}`")
    report_lines.append("")
    report_lines.append("## Notes For Explainable Scoring")
    report_lines.append("")
    report_lines.append("- Use only `skill_taxonomy_refined.yml` for direct skill overlap scoring.")
    report_lines.append("- Use role/version/capability files as auxiliary explainability signals, not as core overlap matches.")
    report_lines.append("- Keep alias normalization and taxonomy expansion as separate steps.")
    report_lines.append("")
    report_lines.append("## Main Review Points")
    report_lines.append("")
    report_lines.append("- SQL-family canonical merge candidates: `mssql`, `ms sql server`, `microsoft sql server` -> `sql server`.")
    report_lines.append("- Security-family boundary cases: `information security`, `system security`, `security management`.")
    report_lines.append("- Role/tool ambiguity: `oracle enterprise manager`, `sql developer`.")
    output_report.parent.mkdir(parents=True, exist_ok=True)
    output_report.write_text("\n".join(report_lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Refine first-pass skill ontology into scoring-friendly slim ontology.")
    parser.add_argument("--input-taxonomy", default="config/skill_taxonomy.yml")
    parser.add_argument("--input-aliases", default="config/skill_aliases.yml")
    parser.add_argument("--input-review", default="config/skill_review_required.yml")
    parser.add_argument("--output-taxonomy", default="config/skill_taxonomy_refined.yml")
    parser.add_argument("--output-roles", default="config/skill_role_candidates.yml")
    parser.add_argument("--output-versions", default="config/versioned_skills.yml")
    parser.add_argument("--output-capabilities", default="config/skill_capability_phrases.yml")
    parser.add_argument("--output-review", default="config/skill_review_required_refined.yml")
    parser.add_argument("--output-report", default="docs/skill_ontology_refinement.md")
    parser.add_argument("--mongo-uri", default=None)
    parser.add_argument("--mongo-db", default=None)
    args = parser.parse_args()

    load_dotenv()
    mongo_uri = args.mongo_uri or os.getenv("MONGODB_URI")
    mongo_db = args.mongo_db or os.getenv("MONGODB_DB", "resume_matching")
    if not mongo_uri:
        raise RuntimeError("MONGODB_URI is required (.env or --mongo-uri).")

    refine(
        taxonomy_path=Path(args.input_taxonomy),
        alias_path=Path(args.input_aliases),
        review_path=Path(args.input_review),
        output_taxonomy=Path(args.output_taxonomy),
        output_roles=Path(args.output_roles),
        output_versions=Path(args.output_versions),
        output_capabilities=Path(args.output_capabilities),
        output_review=Path(args.output_review),
        output_report=Path(args.output_report),
        mongo_uri=mongo_uri,
        mongo_db=mongo_db,
    )

    print(f"Generated: {args.output_taxonomy}")
    print(f"Generated: {args.output_roles}")
    print(f"Generated: {args.output_versions}")
    print(f"Generated: {args.output_capabilities}")
    print(f"Generated: {args.output_review}")
    print(f"Generated: {args.output_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
