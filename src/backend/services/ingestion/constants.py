"""Shared constants for ingestion pipeline."""

from __future__ import annotations

PARSING_VERSION_TEMPLATE = "v4-{parser_mode}-ontology"
PARSING_VERSION_STRUCTURED = "v4-structured-ontology"
NORMALIZATION_VERSION = "norm-v6-substring"
TAXONOMY_VERSION = "taxonomy-v5-suri"
EMBEDDING_TEXT_VERSION = "emb-v2-core-skill"
EXPERIENCE_YEARS_METHOD = "month-union-v1"

# Sneha category -> canonical skill mapping.
SNEHA_CATEGORY_SKILL_MAP: dict[str, str] = {
    "INFORMATION-TECHNOLOGY": "information technology",
    "ACCOUNTANT": "accounting",
    "ENGINEERING": "engineering",
    "HR": "human resources",
    "BANKING": "banking",
    "FINANCE": "finance",
    "CONSULTANT": "consulting",
    "DIGITAL-MEDIA": "digital media",
    "DESIGNER": "design",
    "HEALTHCARE": "healthcare",
    "BUSINESS-DEVELOPMENT": "business development",
    "SALES": "sales",
    "PUBLIC-RELATIONS": "public relations",
    "TEACHER": "teaching",
    "ADVOCATE": "legal",
    "AVIATION": "aviation",
    "FITNESS": "fitness",
    "CHEF": "culinary",
    "CONSTRUCTION": "construction",
    "ARTS": "arts",
    "APPAREL": "apparel",
    "BPO": "bpo",
    "AGRICULTURE": "agriculture",
    "AUTOMOBILE": "automotive",
}
