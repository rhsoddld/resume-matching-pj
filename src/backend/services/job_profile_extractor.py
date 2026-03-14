from __future__ import annotations

from dataclasses import dataclass, field
import re

from backend.core.collections import dedupe_preserve
from backend.services.skill_ontology import RuntimeSkillOntology


_SKILL_SPLIT_RE = re.compile(r"[,\n;/|]+")
_SKILL_TOKEN_RE = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9+.#-]{1,}")
_NGRAM_TOKEN_RE = re.compile(r"[a-zA-Z0-9+.#-]+")
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
    "need",
    "needs",
    "someone",
    "somebody",
    "their",
    "them",
    "who",
    "that",
    "this",
    "these",
    "those",
    "can",
    "could",
    "should",
    "must",
    "work",
    "works",
    "working",
    "used",
    "using",
    "tool",
    "tools",
    "career",
    "early",
    "entry",
    "level",
    "interpret",
    "interpreting",
    "dataset",
    "datasets",
    "we",
    "are",
    "is",
    "am",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "its",
    "mainly",
    "mostly",
    "only",
    "just",
    "on",
    "at",
    "to",
    "of",
    "in",
    "by",
    "as",
    "would",
    "should",
    "helpful",
    "familiarity",
    "multiple",
    "connect",
    "building",
    "has",
    "have",
    "had",
    "looking",
}
_SENIORITY_KEYWORDS = ("intern", "junior", "mid", "senior", "lead", "staff", "principal")
_MAX_PHRASE_WORDS = 4
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]\s+")
_ROLE_PATTERNS = (
    "backend engineer",
    "backend developer",
    "software engineer",
    "data engineer",
    "data scientist",
    "machine learning engineer",
    "devops engineer",
    "platform engineer",
    "frontend engineer",
    "full stack engineer",
    "hr manager",
    "hr coordinator",
    "recruiter",
    "project manager",
    "product manager",
    "database administrator",
)
_MUST_CUES = ("must", "required", "essential", "need to", "needs to")
_NICE_CUES = ("nice to have", "preferred", "plus", "good to have")
_FOCUS_CUES = ("main focus", "primarily", "mainly", "core focus")
_FAMILIARITY_CUES = ("familiarity", "exposure", "understanding", "awareness")
_PHRASE_SKILL_HINTS = {
    "analyze business data": ["data analysis", "business analysis"],
    "interpreting datasets": ["data analysis"],
    "generate reports": ["reporting"],
    "build dashboards": ["reporting", "data visualization"],
    "business data": ["data analysis"],
    "backend of web applications": ["backend", "web", "api"],
    "connect multiple systems": ["api", "integration", "microservices"],
    "deployment environments": ["deployment", "devops", "cloud"],
    "modern deployment environments": ["deployment", "devops", "cloud"],
}
_PHRASE_CAPABILITY_HINTS = {
    "backend of web applications": "backend development",
    "web applications": "web application development",
    "connect multiple systems": "system integration",
    "connect systems": "system integration",
    "services that connect": "api/service connectivity",
    "deployment environments": "deployment environment understanding",
    "modern deployment environments": "deployment environment understanding",
    "container": "devops / cloud / container familiarity",
    "cloud": "devops / cloud / container familiarity",
    "devops": "devops / cloud / container familiarity",
}
_STRENGTH_PRIORITY = {
    "must have": 4,
    "main focus": 3,
    "nice to have": 2,
    "familiarity": 1,
    "unknown": 0,
}
_ONTOLOGY_MAX_NGRAM = 4


@dataclass
class QuerySignal:
    name: str
    strength: str
    signal_type: str


@dataclass
class JobProfile:
    required_skills: list[str]
    expanded_skills: list[str]
    required_experience_years: float | None
    preferred_seniority: str | None
    job_category: str | None = None
    related_skills: list[str] = field(default_factory=list)
    filters: dict[str, str | float] = field(default_factory=dict)
    query_text_for_embedding: str = ""
    confidence: float = 0.0
    roles: list[str] = field(default_factory=list)
    skill_signals: list[QuerySignal] = field(default_factory=list)
    capability_signals: list[QuerySignal] = field(default_factory=list)
    lexical_query: str = ""
    semantic_query_expansion: list[str] = field(default_factory=list)
    metadata_filters: dict[str, str | float] = field(default_factory=dict)
    signal_quality: dict[str, float | int] = field(default_factory=dict)
    fallback_used: bool = False
    fallback_reason: str | None = None
    fallback_rationale: str | None = None
    fallback_trigger: dict[str, str | float | bool] = field(default_factory=dict)


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
        cleaned_words = [w for w in cleaned.split(" ") if w]
        stopword_count = sum(1 for w in cleaned_words if w in _SKILL_STOPWORDS)
        if (
            cleaned
            and len(cleaned) <= 64
            and len(cleaned_words) <= _MAX_PHRASE_WORDS
            and stopword_count <= 1
        ):
            candidates.append(cleaned)
        for token in _SKILL_TOKEN_RE.findall(cleaned):
            if token in _SKILL_STOPWORDS:
                continue
            candidates.append(token)
    return dedupe_preserve(candidates)


def _normalize_ontology_text(value: str) -> str:
    token = value.strip().lower()
    token = re.sub(r"\s+", " ", token)
    token = token.replace("&", " and ")
    token = re.sub(r"\s+", " ", token)
    return token.strip(" ,;:/|")


def _extract_ontology_candidates(job_description: str, ontology: RuntimeSkillOntology | None) -> list[str]:
    if ontology is None or not job_description:
        return []

    vocab = set(ontology.alias_to_canonical.keys()).union(set(ontology.core_taxonomy.keys()))
    if not vocab:
        return []

    lowered = _normalize_ontology_text(job_description)
    words = [w for w in _NGRAM_TOKEN_RE.findall(lowered) if w]
    if not words:
        return []

    hits: list[str] = []
    max_size = min(_ONTOLOGY_MAX_NGRAM, len(words))
    for size in range(max_size, 0, -1):
        for idx in range(0, len(words) - size + 1):
            phrase = " ".join(words[idx : idx + size]).strip()
            if not phrase or phrase not in vocab:
                continue
            canonical = ontology.alias_to_canonical.get(phrase, phrase)
            if canonical and canonical not in _SKILL_STOPWORDS:
                hits.append(canonical)
    return dedupe_preserve(hits)


def _inject_phrase_skill_hints(job_description: str, candidates: list[str]) -> list[str]:
    lowered = job_description.lower()
    hinted = list(candidates)
    for phrase, hints in _PHRASE_SKILL_HINTS.items():
        if phrase in lowered:
            hinted.extend(hints)
    return dedupe_preserve(hinted)


def _filter_noisy_terms(terms: list[str]) -> list[str]:
    filtered: list[str] = []
    for term in terms:
        if not isinstance(term, str):
            continue
        token = term.strip().lower()
        token = re.sub(r"[^\w\s+#.-]", " ", token)
        token = re.sub(r"\s+", " ", token).strip(" .,-")
        if not token:
            continue
        if token in _SKILL_STOPWORDS:
            continue
        words = [w for w in token.split(" ") if w]
        if len(words) == 1 and words[0] in _SKILL_STOPWORDS:
            continue
        if len(words) > _MAX_PHRASE_WORDS:
            continue
        stopword_count = sum(1 for w in words if w in _SKILL_STOPWORDS)
        if stopword_count > 1:
            continue
        # Single-token terms keep useful skill nouns while filtering obvious noise.
        if len(words) == 1:
            word = words[0]
            if len(word) <= 2:
                continue
            if len(word) < 4 and word not in {"api", "sql"}:
                continue
        filtered.append(token)
    return dedupe_preserve(filtered)


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


def _sentences(job_description: str) -> list[str]:
    parts = [p.strip().lower() for p in _SENTENCE_SPLIT_RE.split(job_description or "") if p.strip()]
    return parts or [job_description.lower()]


def _infer_strength_from_sentence(sentence: str) -> str:
    if any(cue in sentence for cue in _MUST_CUES):
        return "must have"
    if any(cue in sentence for cue in _FOCUS_CUES):
        return "main focus"
    if any(cue in sentence for cue in _NICE_CUES):
        return "nice to have"
    if any(cue in sentence for cue in _FAMILIARITY_CUES):
        return "familiarity"
    return "unknown"


def _match_strength_for_term(term: str, sentences: list[str], default_strength: str) -> str:
    best = default_strength
    term_words = [w for w in term.lower().split(" ") if w]
    for sentence in sentences:
        if all(word in sentence for word in term_words):
            strength = _infer_strength_from_sentence(sentence)
            if _STRENGTH_PRIORITY.get(strength, 0) > _STRENGTH_PRIORITY.get(best, 0):
                best = strength
    return best


def _infer_role_phrase(job_description: str) -> str | None:
    lowered = job_description.lower()
    for pattern in _ROLE_PATTERNS:
        if pattern in lowered:
            return pattern
    return None


def _infer_roles(
    job_description: str,
    role_phrase: str | None,
    ontology: RuntimeSkillOntology | None,
) -> list[str]:
    lowered = job_description.lower()
    roles: list[str] = []
    if role_phrase:
        roles.append(role_phrase)
    if ontology is not None:
        role_vocab = sorted(ontology.role_candidates, key=lambda r: len(r), reverse=True)
        for role in role_vocab:
            if role and role in lowered:
                roles.append(role)
    if "backend" in lowered:
        roles.append("backend engineer")
    if "backend" in lowered and "web application" in lowered:
        roles.append("backend web application developer")
    if ("integration" in lowered) or ("connect multiple systems" in lowered) or ("services that connect" in lowered):
        roles.append("integration/service engineer")
    return dedupe_preserve([r for r in roles if r])


def _infer_job_category(
    *,
    job_description: str,
    role_phrase: str | None,
    required_skills: list[str],
    category_override: str | None,
) -> str | None:
    if category_override:
        return category_override

    if role_phrase:
        return role_phrase

    lowered = job_description.lower()
    joined_skills = " ".join(required_skills)
    role_or_desc = " ".join(filter(None, [role_phrase, lowered, joined_skills]))

    if any(term in role_or_desc for term in ("hr", "human resources", "recruit", "talent acquisition", "people operations")):
        return "human resources"
    if any(term in role_or_desc for term in ("data scientist", "machine learning", "analytics", "data science")):
        return "data science"
    if any(term in role_or_desc for term in ("backend engineer", "software engineer", "developer", "devops", "platform engineer")):
        return "information technology"
    if any(term in role_or_desc for term in ("database administrator", "sql developer", "database")):
        return "database"
    return None


def _build_query_text_for_embedding(
    *,
    role_phrase: str | None,
    job_category: str | None,
    required_skills: list[str],
    related_skills: list[str],
    seniority_hint: str | None,
) -> str:
    ordered_terms = dedupe_preserve(
        [
            role_phrase or "",
            job_category or "",
            *(required_skills or []),
            *(related_skills or []),
            seniority_hint or "",
        ]
    )
    return " ".join(term.strip() for term in ordered_terms if isinstance(term, str) and term.strip())


def _extract_capability_signals(
    job_description: str,
    sentences: list[str],
    ontology: RuntimeSkillOntology | None,
) -> list[QuerySignal]:
    lowered = job_description.lower()
    out: list[QuerySignal] = []
    for phrase, capability in _PHRASE_CAPABILITY_HINTS.items():
        if phrase not in lowered:
            continue
        strength = _match_strength_for_term(capability, sentences, default_strength="familiarity")
        out.append(QuerySignal(name=capability, strength=strength, signal_type="capability"))
    if ontology is not None:
        for capability in sorted(ontology.capability_phrases, key=lambda c: len(c), reverse=True):
            if capability and capability in lowered:
                strength = _match_strength_for_term(capability, sentences, default_strength="familiarity")
                out.append(QuerySignal(name=capability, strength=strength, signal_type="capability"))
    return _dedupe_signals(out)


def _build_skill_signals(required_skills: list[str], sentences: list[str]) -> list[QuerySignal]:
    signals = [
        QuerySignal(
            name=skill,
            strength=_match_strength_for_term(skill, sentences, default_strength="must have"),
            signal_type="skill",
        )
        for skill in required_skills
    ]
    return _dedupe_signals(signals)


def _dedupe_signals(signals: list[QuerySignal]) -> list[QuerySignal]:
    by_name: dict[str, QuerySignal] = {}
    for signal in signals:
        key = signal.name.strip().lower()
        if not key:
            continue
        existing = by_name.get(key)
        if existing is None:
            by_name[key] = signal
            continue
        if _STRENGTH_PRIORITY.get(signal.strength, 0) > _STRENGTH_PRIORITY.get(existing.strength, 0):
            by_name[key] = signal
    return list(by_name.values())


def _build_lexical_query(
    *,
    roles: list[str],
    skill_signals: list[QuerySignal],
    capability_signals: list[QuerySignal],
) -> str:
    ordered_skills = sorted(skill_signals, key=lambda s: _STRENGTH_PRIORITY.get(s.strength, 0), reverse=True)
    ordered_caps = sorted(capability_signals, key=lambda s: _STRENGTH_PRIORITY.get(s.strength, 0), reverse=True)
    parts = [*roles, *(s.name for s in ordered_skills), *(c.name for c in ordered_caps)]
    return " ".join(dedupe_preserve([p for p in parts if p]))


def _build_semantic_query_expansion(
    *,
    roles: list[str],
    required_skills: list[str],
    related_skills: list[str],
    capability_signals: list[QuerySignal],
) -> list[str]:
    parts = [*roles, *required_skills, *related_skills, *(c.name for c in capability_signals)]
    return dedupe_preserve([p for p in parts if p])


def _compute_signal_quality(skill_signals: list[QuerySignal], capability_signals: list[QuerySignal]) -> dict[str, float | int]:
    total = len(skill_signals) + len(capability_signals)
    unknown = sum(1 for s in [*skill_signals, *capability_signals] if s.strength == "unknown")
    must_have = sum(1 for s in [*skill_signals, *capability_signals] if s.strength == "must have")
    familiarity = sum(1 for s in [*skill_signals, *capability_signals] if s.strength == "familiarity")
    unknown_ratio = round((unknown / total), 4) if total > 0 else 0.0
    return {
        "total_signals": total,
        "unknown_signals": unknown,
        "must_have_signals": must_have,
        "familiarity_signals": familiarity,
        "unknown_ratio": unknown_ratio,
    }


def _compute_query_confidence(
    *,
    required_skills: list[str],
    job_category: str | None,
    preferred_seniority: str | None,
    required_experience_years: float | None,
    query_text_for_embedding: str,
) -> float:
    score = 0.0
    if required_skills:
        score += 0.35
    if len(required_skills) >= 2:
        score += 0.15
    if job_category:
        score += 0.2
    if preferred_seniority:
        score += 0.1
    if required_experience_years is not None:
        score += 0.1
    if query_text_for_embedding.strip():
        score += 0.1
    return round(max(0.0, min(1.0, score)), 3)


def build_job_profile(
    job_description: str,
    ontology: RuntimeSkillOntology | None,
    *,
    category_override: str | None = None,
    min_experience_years: float | None = None,
) -> JobProfile:
    parsed_sentences = _sentences(job_description)
    raw_candidates = _extract_job_skill_candidates(job_description)
    raw_candidates = _inject_phrase_skill_hints(job_description, raw_candidates)
    filtered_candidates = _filter_noisy_terms(raw_candidates)
    ontology_candidates = _extract_ontology_candidates(job_description, ontology)
    if ontology is None:
        required_skills = filtered_candidates
        expanded_skills = raw_candidates
    else:
        seed_candidates = dedupe_preserve([*ontology_candidates, *filtered_candidates])
        normalized = ontology.normalize(raw_skills=seed_candidates, abilities=[])
        known_terms = set(ontology.core_taxonomy.keys()).union(set(ontology.alias_to_canonical.values()))
        known_canonical = [skill for skill in normalized.canonical_skills if skill in known_terms]
        required_skills = normalized.core_skills or known_canonical or filtered_candidates
        expanded_skills = normalized.expanded_skills or required_skills

    required_skills = dedupe_preserve(required_skills)
    expanded_skills = dedupe_preserve(expanded_skills)
    related_skills = [skill for skill in expanded_skills if skill not in set(required_skills)]
    preferred_seniority = _extract_preferred_seniority(job_description)
    role_phrase = _infer_role_phrase(job_description)
    roles = _infer_roles(job_description, role_phrase, ontology)
    job_category = _infer_job_category(
        job_description=job_description,
        role_phrase=role_phrase,
        required_skills=required_skills,
        category_override=category_override,
    )
    filters: dict[str, str | float] = {}
    if category_override:
        filters["category"] = category_override
    if min_experience_years is not None:
        filters["min_experience_years"] = float(min_experience_years)
    if preferred_seniority is not None:
        filters["seniority_hint"] = preferred_seniority
    metadata_filters = dict(filters)
    skill_signals = _build_skill_signals(required_skills, parsed_sentences)
    capability_signals = _extract_capability_signals(job_description, parsed_sentences, ontology)
    lexical_query = _build_lexical_query(
        roles=roles,
        skill_signals=skill_signals,
        capability_signals=capability_signals,
    )
    semantic_query_expansion = _build_semantic_query_expansion(
        roles=roles,
        required_skills=required_skills,
        related_skills=related_skills,
        capability_signals=capability_signals,
    )
    signal_quality = _compute_signal_quality(skill_signals, capability_signals)
    query_text_for_embedding = _build_query_text_for_embedding(
        role_phrase=role_phrase,
        job_category=job_category,
        required_skills=required_skills,
        related_skills=semantic_query_expansion or related_skills,
        seniority_hint=preferred_seniority,
    )
    required_experience_years = _extract_required_experience_years(job_description)
    confidence = _compute_query_confidence(
        required_skills=required_skills,
        job_category=job_category,
        preferred_seniority=preferred_seniority,
        required_experience_years=required_experience_years,
        query_text_for_embedding=query_text_for_embedding or job_description,
    )

    return JobProfile(
        required_skills=required_skills,
        expanded_skills=expanded_skills,
        required_experience_years=required_experience_years,
        preferred_seniority=preferred_seniority,
        job_category=job_category,
        related_skills=related_skills,
        filters=filters,
        query_text_for_embedding=query_text_for_embedding or job_description,
        confidence=confidence,
        roles=roles,
        skill_signals=skill_signals,
        capability_signals=capability_signals,
        lexical_query=lexical_query,
        semantic_query_expansion=semantic_query_expansion,
        metadata_filters=metadata_filters,
        signal_quality=signal_quality,
    )
