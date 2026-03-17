# Resume Ingestion & Normalization Flow

## Scope

| Item | Details |
|------|------|
| **Source datasets** | `snehaanbhawal/resume-dataset` (`Resume.csv`), `suriyaganesh/resume-dataset-structured` (`01~05_*.csv`) |
| **Target stores** | MongoDB `candidates`, Milvus `candidate_embeddings` |
| **Ingestion script** | `scripts/ingest_resumes.py` (wrapper) → `src/backend/services/ingest_resumes.py` |
| **Preprocessing modules** | `src/backend/services/ingestion/preprocessing.py`, `constants.py`, `transformers.py`, `state.py` |

---

## Pipeline Summary

```
Raw CSV
  ↓ 1. Load rows
  ↓ 2. Parse + normalize (regex, spaCy, dateparser)
  ↓ 3. Map → unified Candidate schema
  ↓ 4. Build embedding_text
  ↓ 5. Compute normalization_hash
  ↓ 6. Upsert changed docs only → MongoDB (--target mongo)
  ↓ 7. Embed changed docs only → Milvus (--target milvus)
```

---

## Ingestion API Surface (Code-Aligned)

You can trigger ingestion via `POST /api/ingestion/resumes`. **This API is for batch loading; it is not a realtime “register one resume” upload API.**

Key request schema fields:
- `source`: `sneha | suri | all`
- `target`: `mongo | milvus | all`
- `milvus_from_mongo`, `force_mongo_upsert`, `force_reembed`, `dry_run`
- `parser_mode`: `rule | spacy | hybrid`
- `csv_chunk_size`, `batch_size`, `sneha_limit`, `suri_limit`
- `async_mode`

Operational guards:
- `X-API-Key` validation (required when `INGESTION_API_KEY` is set)
- Per-minute request rate limit (`ingestion_rate_limit_per_minute`)
- Async execution policy (`ingestion_allow_async`)

Implementation:
- `src/backend/api/ingestion.py`
- `src/backend/schemas/ingestion.py`

---

## Normalization Rules

### 0) Programmatic parsing stack (without an LLM)

| Tool | Coverage | Cost |
|------|---------|------|
| `regex + section split` | Split Skills / Education / Experience sections | Free |
| `spaCy + NER` | Enrich entities (company/date/name) (`en_core_web_sm` family) | Free |
| `dateparser` | Normalize diverse date formats | Free |
| `pdfplumber` + `pdfminer.six` | PDF text extraction utilities | Free |

> Integrated in `src/backend/services/resume_parsing.py`, and controlled in ingestion via `--parser-mode`.  
> `hybrid` uses a **conditional enrichment** strategy: skip spaCy when rule-based output is sufficient.

Ingestion preprocessing/transforms are split by responsibility as follows.

| File | Responsibility |
|------|------|
| `preprocessing.py` | normalize text/skills/dates, compute experience years, category imputation, build embedding text |
| `transformers.py` | map row/object → `ParsedEducation`, `ParsedExperienceItem`; inject Sneha category skills; generate synthetic resume text |
| `constants.py` | parsing/normalization/embedding version constants + Sneha category mapping |
| `state.py` | compute normalization/embedding hashes, adjust ingestion version, manage candidate state keys |

**Parser setup (recommended):**

```bash
# spaCy NER model
python -m spacy download en_core_web_sm

```

> If the model is missing, that parser automatically falls back and ingestion continues.

### 1) Common text cleaning (`clean_text`)

| Input | Output |
|------|---------|
| `None`, `NaN`, `""` | `None` |
| `"nan"` / `"none"` / `"null"` / `"na"` / `"n/a"` (case-insensitive) | `None` |
| Repeated whitespace | Collapse to a single space |

### 2) Candidate ID normalization (`normalize_identifier`)

| Dataset | Source field | Rule | Example |
|---------|---------|---------|------|
| Sneha | `ID` | `"sneha-{ID}"` | `16852973` → `sneha-16852973` |
| Suri | `person_id` | `"suri-{person_id}"` | `408` → `suri-408` |

> Purpose: prevent ID collisions across datasets and strengthen identifiability via source prefixes.

### 3) Skill normalization (`normalize_skill_list` + ontology normalize)

| Step | Details |
|---------|------|
| Whitespace cleanup | trim and remove repeated whitespace |
| Lowercasing | ignore casing for synonym mapping |
| Deduplication | stable dedupe (preserve order) |
| `parsed.skills` | cleaned list based on raw text |
| `parsed.normalized_skills` | lexical-normalized output |
| `parsed.canonical_skills/core_skills/expanded_skills` | ontology canonicalization + taxonomy expansion output |

### 4) Date normalization (`normalize_month`)

| Accepted input format | Stored format |
|-------------|---------|
| `MM/YYYY` | `YYYY-MM` |
| `YYYY/MM` | `YYYY-MM` (if `/00`, coerce to `YYYY-01`) |
| `YYYY-MM` | `YYYY-MM` |
| `Mon YYYY` (e.g., `Jan 2020`) | `YYYY-MM` |
| `Month YYYY` (e.g., `January 2020`) | `YYYY-MM` |
| `Season YYYY` (e.g., `Fall 2014`) | `YYYY-MM` (`Fall/Autumn=09`, `Spring=03`, `Summer=06`, `Winter=12`) |
| `YYYY` (year only) | `YYYY-01` |
| `"Present"` / `"Current"` / `"Now"` | `"present"` |

Additional rules:
- Preprocess by removing prefixes: `from/since/starting/start/beginning/as of/effective ...`
- Treat incomplete values like `08/YY`, `00/00`, `unknown`, `n/a` as `None`
- If both `dateparser` and rule parsing fail, converge to `None` rather than keeping raw strings
- Normalize inconsistent resume date formats (`from 2003`, `Fall 2014`, `2014/00`) to `YYYY-MM`

### 5) Experience years / seniority derivation

| Field | Computation |
|------|---------|
| `parsed.experience_years` | sum months across `experience_items[].start_date ~ end_date` → `/ 12` (1 decimal place) |
| `parsed.seniority_level` | `< 2y` → `junior` / `< 5y` → `mid` / `< 8y` → `senior` / `≥ 8y` → `lead` |

### 6) Embedding text composition (`build_embedding_text`)

| Component | Order | Limit |
|---------|------|------|
| `Name: {name}` | 1 | include if present |
| `Category: {category}` | 2 | Sneha original or Suri rule-based imputation |
| `Summary: {summary}` | 3 | |
| `Core/Specialized/Expanded skills` | 4 | apply per-section caps |
| `Capabilities` | 5 | top capability phrases |
| `Experience titles: {titles[:20]}` | 6 | dedupe |
| Final | — | truncate to max 4,000 chars |

### 7) Incremental processing hashes (`normalization_hash`, `embedding_hash`)

| Field | Meaning |
|------|------|
| `ingestion.normalization_hash` | hash snapshot of normalized output (used to detect unchanged docs) |
| `ingestion.embedding_hash` | hash of the last embedding sync |
| `ingestion.embedding_upserted_at` | last upsert time into Milvus |

Default behavior:
- If `normalization_hash` is unchanged, skip Mongo upsert
- If `embedding_hash == normalization_hash`, skip re-embedding
- Force reprocessing via `--force-mongo-upsert`, `--force-reembed`

---

## Source-to-target field mapping

### Sneha (`Resume.csv`)

| Source field | Candidate target field | Notes |
|---------|-----------------|------|
| `ID` | `candidate_id`, `source_keys.ID` | prefix `sneha-` |
| `Resume_str` | `raw.resume_text`, `parsed.summary` (first 280 chars) | embedding fallback |
| `Resume_html` | `raw.resume_html` | |
| `Category` | `category` | |
| `Resume_str` | `metadata.name/email/phone` | regex + spaCy |
| `Resume_str` | `parsed.skills`, `parsed.normalized_skills` | regex + spaCy enrichment |
| `Resume_str` | `parsed.education[]`, `parsed.experience_items[]` | section-based parsing + spaCy enrichment |
| (derived) | `parsed.experience_years`, `parsed.seniority_level` | computed from `experience_items` |

### Suri (Structured CSV)

| Source file/field | Candidate target field | Notes |
|-------------|-----------------|------|
| `01_people.name` | `metadata.name` | |
| `01_people.email/phone/linkedin` | `metadata.email/phone/linkedin` | |
| `02_abilities.ability` | `parsed.abilities` | |
| `05_person_skills.skill` | `parsed.skills`, `parsed.normalized_skills` | |
| `03_education.program` | `parsed.education[].degree` | |
| `03_education.institution` | `parsed.education[].institution` | |
| `03_education.start_date` | `parsed.education[].start_date` | apply `normalize_month` |
| `03_education.location` | `parsed.education[].location` | |
| `04_experience.title` | `parsed.experience_items[].title` | |
| `04_experience.firm` | `parsed.experience_items[].company` | |
| `04_experience.start_date/end_date` | `parsed.experience_items[].start_date/end_date` | apply `normalize_month` |
| `04_experience.location` | `parsed.experience_items[].location` | |
| (derived) | `parsed.experience_years`, `parsed.seniority_level` | `estimate_experience_years` |
| (derived, first valid location) | `metadata.location` | |
| (derived) | `category` | inferred by `impute_category_rule_based` using experience titles + core_skills |

---

## Split ingestion by infrastructure (Mongo / Milvus split)

| Option | Command | Description |
|------|------|------|
| Mongo only | `--target mongo` | CSV → parse → MongoDB |
| Milvus only (from Mongo) | `--target milvus --milvus-from-mongo` | MongoDB → embed → Milvus |
| Ingest both | `--target all` | CSV → parse → MongoDB + Milvus |
| Parser mode | `--parser-mode rule|spacy|hybrid` | choose Sneha parsing mode (`hybrid`: enrich only when rule output is insufficient) |
| CSV streaming chunk size | `--csv-chunk-size` | read large CSVs in chunks to reduce memory use |
| Force Mongo re-upsert | `--force-mongo-upsert` | upsert even when hashes are unchanged |
| Force re-embedding | `--force-reembed` | re-embed even when hashes are unchanged |
| Dry-run | `--dry-run` | show batch plan without writing to DB/vector store |

---

## Performance design

| Item | Strategy |
|------|------|
| CSV loading | streaming processing via `read_csv(chunksize=...)` |
| Suri auxiliary CSV joins | early-stop scans when ID ranges exceed targets (leverages `person_id` ordering) |
| Parser performance | initialize spaCy once and reuse (avoid per-row reloads) |
| Hybrid optimization | skip spaCy when rule-based output is sufficient (conditional enrichment) |
| Parser fault tolerance | disable spaCy in-process on runtime failures and continue |
| OpenAI embeddings | batched calls (`embed_texts`, `batch_size=32`) |
| MongoDB upsert | `bulk_write` (ordered=False) |
| Milvus upsert | delete then insert for the same `(source_dataset, candidate_id)` |
| Milvus safety | ensure `collection.load()` before delete (prevents `collection not loaded` in some environments) |
| Reduced rerun cost | hash-based incremental processing skips unchanged docs |

---

## Recommended run order

```bash
# Step 1: Ingest into MongoDB
python3 scripts/ingest_resumes.py \
  --source all --target mongo --parser-mode hybrid \
  --sneha-limit 200 --suri-limit 500

# Step 2: Ingest into Milvus
python3 scripts/ingest_resumes.py \
  --source all --target milvus --milvus-from-mongo \
  --sneha-limit 200 --suri-limit 500
```

---

## Operational snapshot (2026-03-13)

| Item | Result |
|------|------|
| Mongo reload | upsert completed: `Sneha 2484 + Suri 3000 = 5484` |
| Date normalization quality | `invalid_dates_edu = 0`, `invalid_dates_exp = 0` (both datasets) |
| Milvus incremental embedding | `seen=5484`, `embedded=5484`, `embed_skipped=0` |
| Mongo↔embedding sync | `embedding_hash null = 0`, `embedding_upserted_at null = 0`, mismatched `normalization_hash == embedding_hash` = `0` |

> Note: Milvus `num_entities` can be larger than the Mongo doc count (stale vectors from prior runs).  
> Current incremental upsert updates only the input `(source_dataset, candidate_id)` set; a full orphan purge is a separate task.

---

## ⚠️ Normalization gap analysis — agentic AI integration view

> **Key decision (ADR-003)**: do not use a generative LLM for ingestion parsing ❌. Null fields are handled by including raw_text context in the RAG pipeline.

### Gap summary table

| Gap ID | Target | Missing fields | Impacted agent(s) | Severity | Mitigation |
|--------|------|-----------|-----------|-------|---------|
| **G-01** | Some Sneha | `experience_years = None`, `seniority_level = None` | ExperienceEvalAgent | 🟡 Medium | keep parser-mode=`hybrid` + fall back to `raw.resume_text` when null |
| **G-02** | Some Sneha | `parsed.experience_items = []` | ExperienceEvalAgent, TechnicalEvalAgent | 🟡 Medium | regex/global date range + spaCy enrichment, then fallback |
| **G-03** | Some Sneha | `parsed.education = []` | ExperienceEvalAgent | 🟡 Medium | expand degree patterns + adjust scoring weights on null |
| **G-04** | Some Suri | missing `category_confidence` + possible rule-based misclassification | SkillMatchingAgent filters, CultureFitAgent | 🟡 Medium | keep `impute_category_rule_based` + multi-evidence category sanity check (abilities/skills/experience) |
| **G-05** | Some Sneha | empty `parsed.skills` (regex failure) | SkillMatchingAgent | 🟡 Medium | spaCy enrichment + `raw.resume_text` fallback |
| **G-06** | Both | limited `SKILL_NORMALIZATION_MAP` rule count | SkillMatchingAgent | 🟡 Medium | gradually expand synonym map (without LLM) |
| **G-07** | Suri | `experience_items[].description = None` | TechnicalEvalAgent, CultureFitAgent | 🟡 Medium | include Abilities text as context |
| **G-08** | Suri | `summary` is generic (`"{role} resume profile"`) | Overall | 🟢 Low | enrich embedding_text using Abilities + Skills (already implemented) |
| **G-09** | Both | inconsistent embedding_text composition | Retriever/Ranking | 🟡 Medium | keep a shared template + tune field weights to reduce bias |

> Mongo live count as of 2026-03-16 (before reload): `G-01=62`, `G-02=62`, `G-03=412`, `G-05=26`  
> After 2026-03-16 parser patch + reload: `G-01=5`, `G-02=6`, `G-03=59`, `G-05=8`
> After 2026-03-16 Sneha abilities rule-extraction: `Sneha abilities=2464/2484 (99.2%)`, `overall abilities=5463/5484 (99.6%)`

### Mitigation strategy (all without LLMs)

```
Ingestion (offline, one-time, LLM ❌)
  current (v3): regex + spaCy + dateparser (hybrid, conditional enrichment)
  fallback: can downgrade to parser-mode=rule
  reruns: use hash comparison to write only changed docs to Mongo/Milvus

RAG Pipeline (at match time)
  happy path: use MongoDB structured fields (skills/experience_items, etc.)
  fallback: if fields are null, include raw.resume_text in CandidateContext
            → agent decides only what it needs with the JD
```

### Per-agent handling of null fields

| Agent | Null scenario | RAG pipeline handling |
|-------|---------|-----------------|
| `SkillMatchingAgent` | Sneha skills empty | include `raw.resume_text` context → agent infers skills vs JD |
| `ExperienceEvalAgent` | Sneha `experience_years=None`, no experience items | include `raw.resume_text` → agent estimates experience from text |
| `TechnicalEvalAgent` | Sneha missing experience descriptions | include `raw.resume_text` → cite stack text |
| `CultureFitAgent` | Suri missing category confidence / possible misclassification | include Abilities + Skills + Experience titles → judge domain fit |
| `RankingAgent` | partial score availability | combine available scores; call out missing fields in explanations |

> `ResumeParsingAgent` is **not operated** (ADR-003). Parsing is completed by ingestion rule-based pipelines; gaps are handled via RAG context.

---

## Legacy Version History (Restored)

This document merges the key version history from the legacy ingestion/normalization design notes.

| Version | normalization_version | taxonomy_version | Key changes | core_skills empty |
|---|---|---|---|---|
| V2 | `norm-v3-ontology` | `taxonomy-v2-refined` | expand ParsedSection skill fields; introduce hash-based incremental processing | 55.0% |
| V3 | `norm-v4-ontology` | `taxonomy-v3-expanded` | expand alias merging; broaden taxonomy coverage | 44.8% |
| V4 | `norm-v5-category` | `taxonomy-v4-domain` | Sneha category -> core skill inject | 12.7% |
| V5 | `norm-v6-substring` | `taxonomy-v5-suri` | introduce substring matching; strengthen taxonomy for Suri DBA-like profiles | 0.5% |

---

## Ontology Analysis Snapshot (Restored)

This document merges key metrics from legacy ontology analysis/refinement notes.

### Dataset coverage (2026-03-16 snapshot)

| Item | Value |
|---|---:|
| total candidates | 5484 |
| docs with `parsed.skills` | 5471 (99.8%) |
| docs with `parsed.abilities` | 5463 (99.6%) |
| docs with `parsed.experience_items.title` | 5459 (99.5%) |
| docs with `category` | 5484 (100.0%) |

### Refinement summary

| Category | Count |
|---|---:|
| slim core taxonomy entries | 66 |
| role-like candidates | 15 |
| versioned skills | 32 |
| capability phrases | 80 |
| review-required refined | 69 |
| canonical merge candidates | 11 |

Refinement principles:
- separate role/tool/capability from core skills
- manage versioned skills as `{raw, canonical, version}`
- treat ambiguous tokens conservatively as review-required

---

## Clean Rebuild Runbook (Restored)

1. Clean Mongo `candidates` collection (use an approach aligned with your ops policy)
2. Ingest into Mongo:
   - `python3 scripts/ingest_resumes.py --source all --target mongo --parser-mode hybrid`
3. Validate:
   - verify `normalization_version/taxonomy_version` consistency
   - check `core_skills empty` ratio
4. Ingest into Milvus:
   - `python3 scripts/ingest_resumes.py --source all --target milvus --milvus-from-mongo --force-reembed`
5. API smoke test:
   - verify `POST /api/jobs/match` output and fallback/fairness metadata
