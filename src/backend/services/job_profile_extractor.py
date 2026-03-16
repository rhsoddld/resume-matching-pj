from __future__ import annotations

from dataclasses import dataclass, field
import re

from backend.core.collections import dedupe_preserve
from backend.services.job_profile.signals import compute_signal_quality, dedupe_signals
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
    "nice",
}
_GENERIC_NON_SKILL_TERMS = {
    "responsibilities",
    "responsibility",
    "requirements",
    "requirement",
    "role",
    "roles",
    "main",
    "focus",
    "focused",
    "field",
    "domain",
    "related",
    "internal",
    "external",
    "across",
    "define",
    "target",
    "targets",
    "evolution",
    "platform",
    "platforms",
    "talent",
    "intelligence",
    "team",
    "teams",
    "engineering",
    "support",
    "supports",
    "supporting",
    "process",
    "processes",
    "hiring",
    "hire",
    "client",
    "clients",
    "guide",
    "guides",
    "guiding",
    "program",
    "programs",
    "solution",
    "solutions",
    "mentor",
    "mentoring",
    "decision",
    "decisions",
    "balancing",
    "reliability",
    "scalability",
    "cost",
    "costs",
    "standards",
    "governance",
    "strong",
    "excellent",
    "communication",
    "regulated",
    "enterprise",
    "equivalent",
    "deep",
    "expertise",
    "include",
    "includes",
    "code",
    "task",
    "tasks",
    "write",
    "under",
    "learn",
    "proven",
    "drive",
    "review",
    "layers",
    "matching",
    "analyst",
    "consultant",
    "consulting",
    "business",
    "operational",
    "improvement",
    "stakeholder",
    "management",
    "programming",
    "software",
    "engineer",
    "foundational",
    "understanding",
    "basics",
    "change",
    "changes",
    "culture",
    "mission",
    "operate",
    "operating",
    "measure",
    "measuring",
    "beyond",
    "become",
    "mere",
    "literacy",
}
_SENIORITY_KEYWORDS = ("intern", "junior", "mid", "senior", "lead", "staff", "principal")
_SINGLE_TERM_WHITELIST = {
    "api",
    "sql",
    "aws",
    "gcp",
    "azure",
    "java",
    "python",
    "scala",
    "spark",
    "docker",
    "kafka",
    "redis",
    "linux",
    "react",
    "node",
    "git",
    "go",
    "rust",
    "ruby",
    "php",
    "swift",
    "kotlin",
    "c",
    "c++",
    "c#",
    "r",
}
_MAX_PHRASE_WORDS = 4
_SENTENCE_SPLIT_RE = re.compile(r"[.!?]\s+")
_MAX_REQUIRED_SKILLS = 18
_MAX_RELATED_SKILLS = 12
_MAX_EMBED_REQUIRED_TERMS = 12
_MAX_EMBED_RELATED_TERMS = 8
_ROLE_EMBED_CAP_EXPANSION: dict[str, tuple[int, int]] = {
    "junior software engineer": (16, 12),
    "senior architect": (16, 12),
}
_ROLE_PATTERNS = (
    "backend engineer",
    "backend developer",
    "junior software engineer",
    "graduate software engineer",
    "associate engineer",
    "software engineer",
    "data engineer",
    "data scientist",
    "machine learning engineer",
    "ml engineer",
    "devops engineer",
    "platform engineer",
    "frontend engineer",
    "full stack engineer",
    "fullstack engineer",
    "qa engineer",
    "qa automation engineer",
    "test automation engineer",
    "business analyst",
    "hr manager",
    "hr coordinator",
    "recruiter",
    "project manager",
    "product manager",
    "database administrator",
    "senior architect",
    "solutions architect",
    "consultant",
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
    # fullstack / web
    "fullstack engineer": ["java", "spring boot", "react", "rest api", "postgresql"],
    "full stack engineer": ["java", "spring boot", "react", "rest api", "postgresql"],
    "fullstack features": ["java", "spring boot", "react", "rest api"],
    # qa / test automation
    "test automation": ["test automation", "selenium", "pytest", "api testing", "ci/cd"],
    "qa automation": ["test automation", "selenium", "pytest", "api testing", "ci/cd"],
    "automated quality gates": ["test automation", "api testing"],
    # ml / ai
    "machine learning engineer": ["machine learning", "python", "pytorch", "feature engineering", "model deployment"],
    "production ml pipelines": ["machine learning", "python", "pytorch", "model deployment"],
    "nlp-powered": ["machine learning", "python"],
    # business analyst
    "business analyst": ["requirements gathering", "stakeholder management", "sql", "reporting", "process mapping"],
    "requirements management": ["requirements gathering", "stakeholder management"],
    "operational improvement": ["process mapping", "reporting"],
    # architect
    "senior architect": ["system architecture", "cloud architecture", "distributed systems", "security by design", "technical leadership"],
    "enterprise-scale architecture": ["system architecture", "cloud architecture", "distributed systems"],
    "modernization programs": ["system architecture", "cloud architecture"],
    "cross-domain architecture strategy": ["system architecture", "distributed systems", "technical leadership"],
    "architecture standards and governance": ["system architecture", "technical leadership", "solution governance"],
    "architecture review practices": ["system architecture", "technical leadership", "security by design"],
    # junior software
    "junior software engineer": ["python", "java", "git", "data structures", "unit testing"],
    "entry-level software engineering": ["python", "java", "git", "data structures", "unit testing"],
    "graduate software engineer": ["python", "java", "git", "data structures", "unit testing"],
    "associate engineer": ["python", "java", "git", "unit testing"],
    "version control": ["git"],
    "cs fundamentals": ["data structures"],
    "unit testing basics": ["unit testing"],
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
    "junior software engineer": "software engineering fundamentals",
    "entry-level software engineering": "software engineering fundamentals",
    "senior architect": "architecture leadership",
    "architecture governance": "architecture leadership",
    "architecture review practices": "architecture leadership",
}
_STRENGTH_PRIORITY = {
    "must have": 4,
    "main focus": 3,
    "nice to have": 2,
    "familiarity": 1,
    "unknown": 0,
}
_ONTOLOGY_MAX_NGRAM = 4
_DATE_LIKE_RE = re.compile(r"\b(?:\d{1,2}/\d{2,4}|19\d{2}|20\d{2})\b")
_HINTED_SKILL_TERMS = {
    hint.strip().lower()
    for hints in _PHRASE_SKILL_HINTS.values()
    for hint in hints
    if isinstance(hint, str) and hint.strip()
}


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
    transferable_skill_score: float = 0.0
    transferable_skill_evidence: list[str] = field(default_factory=list)
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
        if _DATE_LIKE_RE.search(token):
            continue
        if token in _SKILL_STOPWORDS:
            continue
        if token in _GENERIC_NON_SKILL_TERMS:
            continue
        words = [w for w in token.split(" ") if w]
        if len(words) == 1 and words[0] in _SKILL_STOPWORDS:
            continue
        if len(words) > _MAX_PHRASE_WORDS:
            continue
        stopword_count = sum(1 for w in words if w in _SKILL_STOPWORDS)
        if stopword_count > 1:
            continue
        if len(words) >= 4 and token not in _HINTED_SKILL_TERMS:
            continue
        # Single-token terms keep useful skill nouns while filtering obvious noise.
        if len(words) == 1:
            word = words[0]
            if len(word) <= 2:
                continue
            if len(word) < 4 and word not in _SINGLE_TERM_WHITELIST:
                continue
            if word in _GENERIC_NON_SKILL_TERMS:
                continue
        filtered.append(token)
    return dedupe_preserve(filtered)


def _select_required_candidates(
    terms: list[str],
    *,
    literal_candidates: list[str],
    ontology_candidates: list[str],
    sentences: list[str],
) -> list[str]:
    selected: list[str] = []
    literal_set = {token.strip().lower() for token in literal_candidates if isinstance(token, str) and token.strip()}
    ontology_set = {token.strip().lower() for token in ontology_candidates if isinstance(token, str) and token.strip()}
    preferred_strengths = {"must have", "main focus"}

    for term in dedupe_preserve(terms):
        words = [word for word in term.split(" ") if word]
        strength = _match_strength_for_term(term, sentences, default_strength="unknown")

        if term in ontology_set:
            selected.append(term)
            continue
        if term in literal_set and len(words) >= 2:
            selected.append(term)
            continue
        if term in literal_set and term in _SINGLE_TERM_WHITELIST:
            selected.append(term)
            continue
        if strength in preferred_strengths:
            selected.append(term)
            continue
        if strength in {"nice to have", "familiarity"} and term in literal_set and (len(words) >= 2 or term in _SINGLE_TERM_WHITELIST):
            selected.append(term)

    return dedupe_preserve(selected)


def _skill_priority(term: str, *, ontology: RuntimeSkillOntology | None) -> int:
    score = 0
    words = [w for w in term.split(" ") if w]

    if term in _HINTED_SKILL_TERMS:
        score += 4
    if len(words) <= 2:
        score += 1
    if re.search(r"[+#.]|\d", term):
        score += 2

    if ontology is not None:
        canonical = ontology.alias_to_canonical.get(term, term)
        if canonical in ontology.core_taxonomy:
            score += 5
        elif canonical in ontology.alias_to_canonical.values():
            score += 3

    if term in _GENERIC_NON_SKILL_TERMS:
        score -= 6
    if term in _SENIORITY_KEYWORDS:
        score -= 6
    if len(words) >= 3 and term not in _HINTED_SKILL_TERMS:
        score -= 2
    return score


def _drop_fragment_terms(terms: list[str]) -> list[str]:
    phrase_words: set[str] = set()
    for term in terms:
        words = [w for w in term.split(" ") if w]
        if len(words) < 2:
            continue
        for word in words:
            if len(word) >= 4:
                phrase_words.add(word)

    out: list[str] = []
    for term in terms:
        words = [w for w in term.split(" ") if w]
        if len(words) == 1:
            word = words[0]
            if word in _SENIORITY_KEYWORDS:
                continue
            if word in phrase_words and word not in _SINGLE_TERM_WHITELIST:
                continue
        out.append(term)
    return dedupe_preserve(out)


def _compress_skill_terms(
    terms: list[str],
    *,
    ontology: RuntimeSkillOntology | None,
    max_terms: int,
) -> list[str]:
    unique_terms = _filter_noisy_terms(dedupe_preserve(terms))
    if not unique_terms:
        return []

    scored = sorted(
        unique_terms,
        key=lambda term: (
            _skill_priority(term, ontology=ontology),
            min(len(term.split(" ")), _MAX_PHRASE_WORDS),
            len(term),
        ),
        reverse=True,
    )
    selected = [term for term in scored if _skill_priority(term, ontology=ontology) > 0]
    if not selected:
        selected = scored
    compact = _drop_fragment_terms(dedupe_preserve(selected))
    if not compact:
        compact = dedupe_preserve(selected)
    return compact[:max_terms]


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
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
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
    if any(token in lowered for token in ("junior software engineer", "graduate software engineer", "entry-level software engineering", "associate engineer")):
        roles.append("junior software engineer")
    if ("senior architect" in lowered) or ("architecture leadership" in lowered):
        roles.append("senior architect")
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
    required_limit: int = _MAX_EMBED_REQUIRED_TERMS,
    related_limit: int = _MAX_EMBED_RELATED_TERMS,
) -> str:
    required_for_embedding = dedupe_preserve([skill for skill in required_skills if isinstance(skill, str) and skill.strip()])
    required_for_embedding = required_for_embedding[:required_limit]
    related_for_embedding = [
        skill
        for skill in dedupe_preserve(related_skills)
        if skill not in set(required_for_embedding)
    ][:related_limit]
    ordered_terms = dedupe_preserve(
        [
            role_phrase or "",
            job_category or "",
            *required_for_embedding,
            *related_for_embedding,
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
    return dedupe_signals(out)


def _resolve_embed_term_caps(*, roles: list[str], role_phrase: str | None) -> tuple[int, int]:
    active_roles = {role.strip().lower() for role in roles if isinstance(role, str) and role.strip()}
    if role_phrase:
        active_roles.add(role_phrase.strip().lower())
    required_limit = _MAX_EMBED_REQUIRED_TERMS
    related_limit = _MAX_EMBED_RELATED_TERMS
    for role, (role_required, role_related) in _ROLE_EMBED_CAP_EXPANSION.items():
        if role in active_roles:
            required_limit = max(required_limit, role_required)
            related_limit = max(related_limit, role_related)
    return required_limit, related_limit


def _build_skill_signals(required_skills: list[str], sentences: list[str]) -> list[QuerySignal]:
    signals = [
        QuerySignal(
            name=skill,
            strength=_match_strength_for_term(skill, sentences, default_strength="must have"),
            signal_type="skill",
        )
        for skill in required_skills
    ]
    return dedupe_signals(signals)


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


def _compute_transferable_skill_insight(
    *,
    required_skills: list[str],
    related_skills: list[str],
    capability_signals: list[QuerySignal],
    ontology: RuntimeSkillOntology | None,
) -> tuple[float, list[str], list[str]]:
    strength_scores = {
        "must have": 1.0,
        "main focus": 0.85,
        "nice to have": 0.65,
        "familiarity": 0.45,
        "unknown": 0.35,
    }
    capability_score = 0.0
    capability_evidence: list[str] = []
    if capability_signals:
        capability_values = [strength_scores.get(signal.strength, 0.35) for signal in capability_signals]
        capability_score = sum(capability_values) / float(len(capability_values))
        capability_evidence = [
            f"{signal.name} ({signal.strength}) indicates adjacent capability."
            for signal in capability_signals[:6]
            if signal.name
        ]

    adjacent_skills: list[str] = []
    ontology_evidence: list[str] = []
    if ontology is not None:
        adjacent_skills, ontology_evidence = ontology.find_adjacent_skills(required_skills, limit=10)

    related_score = min(1.0, len(set(related_skills)) / 8.0) if related_skills else 0.0
    adjacent_score = min(1.0, len(set(adjacent_skills)) / 6.0) if adjacent_skills else 0.0
    transferable_score = round(
        max(0.0, min(1.0, (capability_score * 0.5) + (adjacent_score * 0.35) + (related_score * 0.15))),
        3,
    )

    evidence = dedupe_preserve([*capability_evidence, *ontology_evidence])[:8]
    return transferable_score, adjacent_skills, evidence


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
    if len(required_skills) > 25:
        score -= 0.2
    elif len(required_skills) > 18:
        score -= 0.1
    return round(max(0.0, min(1.0, score)), 3)


def build_job_profile(
    job_description: str,
    ontology: RuntimeSkillOntology | None,
    *,
    category_override: str | None = None,
    min_experience_years: float | None = None,
    education_override: str | None = None,
    region_override: str | None = None,
    industry_override: str | None = None,
) -> JobProfile:
    parsed_sentences = _sentences(job_description)
    literal_raw_candidates = _extract_job_skill_candidates(job_description)
    raw_candidates = _inject_phrase_skill_hints(job_description, literal_raw_candidates)
    literal_filtered_candidates = _filter_noisy_terms(literal_raw_candidates)
    filtered_candidates = _filter_noisy_terms(raw_candidates)
    ontology_candidates = _extract_ontology_candidates(job_description, ontology)
    required_candidates = _select_required_candidates(
        filtered_candidates,
        literal_candidates=literal_filtered_candidates,
        ontology_candidates=ontology_candidates,
        sentences=parsed_sentences,
    )
    if ontology is None:
        required_skills = _compress_skill_terms(
            required_candidates or filtered_candidates,
            ontology=None,
            max_terms=_MAX_REQUIRED_SKILLS,
        )
        expanded_skills = dedupe_preserve(
            [
                *required_skills,
                *_compress_skill_terms(filtered_candidates, ontology=None, max_terms=_MAX_REQUIRED_SKILLS + _MAX_RELATED_SKILLS),
            ]
        )
    else:
        seed_candidates = dedupe_preserve([*ontology_candidates, *required_candidates])
        normalized = ontology.normalize(raw_skills=seed_candidates, abilities=[])
        known_terms = set(ontology.core_taxonomy.keys()).union(set(ontology.alias_to_canonical.values()))
        known_canonical = [skill for skill in normalized.canonical_skills if skill in known_terms]

        # Prefer ontology-guided core skills, but do not lose raw tokens like
        # concrete languages or tools (e.g., java, react, sql) that may not
        # yet be fully represented in the ontology taxonomy.
        base_required = normalized.core_skills or known_canonical
        if base_required:
            required_skills = dedupe_preserve([*base_required, *required_candidates])
        else:
            required_skills = required_candidates or filtered_candidates
        required_skills = _compress_skill_terms(
            required_skills,
            ontology=ontology,
            max_terms=_MAX_REQUIRED_SKILLS,
        )

        expanded_base = normalized.expanded_skills or base_required or required_skills
        expanded_skills = dedupe_preserve(
            [
                *required_skills,
                *_compress_skill_terms(
                    dedupe_preserve([*expanded_base, *filtered_candidates]),
                    ontology=ontology,
                    max_terms=_MAX_REQUIRED_SKILLS + _MAX_RELATED_SKILLS,
                ),
            ]
        )

    required_skills = dedupe_preserve(required_skills)[:_MAX_REQUIRED_SKILLS]
    expanded_skills = dedupe_preserve(expanded_skills)
    related_skills = [skill for skill in expanded_skills if skill not in set(required_skills)]
    related_skills = _compress_skill_terms(
        related_skills,
        ontology=ontology,
        max_terms=_MAX_RELATED_SKILLS,
    )
    expanded_skills = dedupe_preserve([*required_skills, *related_skills])
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
    if education_override:
        filters["education"] = education_override
    if region_override:
        filters["region"] = region_override
    if industry_override:
        filters["industry"] = industry_override
    if preferred_seniority is not None:
        filters["seniority_hint"] = preferred_seniority
    metadata_filters = dict(filters)
    skill_signals = _build_skill_signals(required_skills, parsed_sentences)
    capability_signals = _extract_capability_signals(job_description, parsed_sentences, ontology)
    transferable_skill_score, adjacent_skills, transferable_skill_evidence = _compute_transferable_skill_insight(
        required_skills=required_skills,
        related_skills=related_skills,
        capability_signals=capability_signals,
        ontology=ontology,
    )
    related_skills = _compress_skill_terms(
        dedupe_preserve(
            [
                *related_skills,
                *(signal.name for signal in capability_signals if signal.name not in set(required_skills)),
                *adjacent_skills,
            ]
        ),
        ontology=ontology,
        max_terms=_MAX_RELATED_SKILLS,
    )
    expanded_skills = dedupe_preserve([*required_skills, *related_skills])
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
    signal_quality = compute_signal_quality(skill_signals, capability_signals)
    signal_quality["transferable_score"] = transferable_skill_score
    signal_quality["transferable_evidence_count"] = len(transferable_skill_evidence)
    required_embed_limit, related_embed_limit = _resolve_embed_term_caps(
        roles=roles,
        role_phrase=role_phrase,
    )
    query_text_for_embedding = _build_query_text_for_embedding(
        role_phrase=role_phrase,
        job_category=job_category,
        required_skills=required_skills,
        related_skills=related_skills,
        seniority_hint=preferred_seniority,
        required_limit=required_embed_limit,
        related_limit=related_embed_limit,
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
        transferable_skill_score=transferable_skill_score,
        transferable_skill_evidence=transferable_skill_evidence,
        signal_quality=signal_quality,
    )
