# ENGINEERING DOCTRINE
Production Engineering Standards for resume-matching-pj

This document defines the engineering rules and development principles used in this project.

The goal is to maintain a consistent, scalable, and production-ready system architecture.

This doctrine follows a **Senior+ Engineering Standard**, focusing on reliability, maintainability,
and system design clarity.

This document is part of the governance layer of the project.

Location:
docs/governance/ENGINEERING_DOCTRINE.md


------------------------------------------------------------
1. Core Engineering Philosophy
------------------------------------------------------------

Development must follow the order below:

1. Architecture
2. Contracts
3. Data Model
4. Implementation
5. Reliability
6. Evaluation

Implementation must never start from code alone.
Architecture and system boundaries must be defined first.



------------------------------------------------------------
2. Repository Structure Doctrine
------------------------------------------------------------

The repository follows a domain-oriented structure.

resume-matching-pj/

config/
Skill taxonomy, alias mappings, normalization rules.

data/
Raw Kaggle datasets and ingestion inputs.

docs/

    adr/
    Architecture Decision Records

    architecture/
    System architecture diagrams

    data-flow/
    Ingestion and retrieval flows

    governance/
    Project governance documents
    - AGENT.md
    - PLAN.md
    - TRACEABILITY.md
    - DESIGN_DOCTRINE.md
    - ENGINEERING_DOCTRINE.md

    ontology/
    Ontology analysis and refinement artifacts

requirements/
Problem statement and requirement definitions

scripts/
Ontology analysis and refinement scripts

src/backend/

    api/
    FastAPI routers

    core/
    settings
    database connections
    startup logic
    vector store

    repositories/
    MongoDB access layer

    schemas/
    Pydantic models

    services/
    ingestion
    parsing
    matching
    scoring
    ontology processing

tests/
pytest test suite

test_api.py
API smoke test script



------------------------------------------------------------
3. Layered Architecture Rule
------------------------------------------------------------

Application logic must follow this separation:

Router → Service → Repository → Database

Router
- HTTP interface
- request validation
- response formatting

Service
- business logic
- orchestration

Repository
- database queries
- persistence abstraction

Database
- storage layer


Routers must NEVER contain business logic.



------------------------------------------------------------
4. Naming Convention
------------------------------------------------------------

File names must reflect domain responsibility.

Avoid generic names:

utils.py
helpers.py
common.py


Preferred naming examples:

resume_parser.py
candidate_matcher.py
embedding_service.py
vector_repository.py
skill_normalizer.py


Naming rules:

files
snake_case

classes
PascalCase

functions
verb_based naming



------------------------------------------------------------
5. Function Design Rule
------------------------------------------------------------

Each function must have a single responsibility.

Bad example:

process_resume()

    parse
    embedding
    storage
    evaluation


Good example:

parse_resume()
generate_embedding()
store_candidate()
evaluate_candidate()


Functions should remain:

small
testable
composable



------------------------------------------------------------
6. Logging Standard
------------------------------------------------------------

print() statements are forbidden.

All logs must use structured logging.

Example:

logger.info(
    "candidate indexed",
    extra={
        "candidate_id": candidate_id,
        "skill_count": len(skills)
    }
)

Log levels:

DEBUG
INFO
WARNING
ERROR
CRITICAL



------------------------------------------------------------
7. Configuration Management
------------------------------------------------------------

Configuration must never be hardcoded.

Use environment variables.

Example:

.env

OPENAI_API_KEY=...
MONGODB_URI=...


Centralized configuration must be implemented.

Example:

settings.py

class Settings(BaseSettings):

    openai_api_key: str
    mongodb_uri: str



------------------------------------------------------------
8. Schema-First Development
------------------------------------------------------------

All API inputs and outputs must be validated with schemas.

Example:

class JobRequest(BaseModel):

    description: str
    skills: list[str]
    experience_level: int


Benefits:

input validation
API consistency
automatic documentation
safer data handling



------------------------------------------------------------
9. AI System Architecture Rule
------------------------------------------------------------

AI systems must separate three stages:

Retrieval
Ranking
Evaluation


Example pipeline:

Candidate Retrieval
↓

Candidate Ranking
↓

Evaluation Metrics


Evaluation logic must not be embedded in retrieval.



------------------------------------------------------------
10. Evaluation Framework
------------------------------------------------------------

The system must include automated evaluation.

Possible approaches:

IR Metrics

NDCG
MAP
MRR

LLM-as-Judge

Rubric Scoring


Evaluation datasets must be versioned.



------------------------------------------------------------
11. Error Handling
------------------------------------------------------------

Silent failures are forbidden.

Bad example:

try:
    run()
except:
    pass


Good example:

try:
    embedding = model.embed(text)

except TimeoutError:

    logger.error("embedding timeout")

    return fallback_embedding(text)



------------------------------------------------------------
12. Dependency Abstraction
------------------------------------------------------------

External providers must be abstracted.

Example interface:

class EmbeddingProvider:

    def embed(text: str) -> list[float]


Implementations:

OpenAIEmbeddingProvider
LocalEmbeddingProvider


This allows provider replacement without modifying core logic.



------------------------------------------------------------
13. Startup Initialization
------------------------------------------------------------

Heavy resources must initialize during application startup.

Bad:

load_model() inside request handler


Good:

model initialized during startup



------------------------------------------------------------
14. Traceability Rule
------------------------------------------------------------

Every implemented feature must map to a requirement ID.

Example:

REQ-01 Resume Ingestion
REQ-02 Candidate Retrieval
REQ-03 Skill Matching
REQ-04 Candidate Ranking
REQ-05 Evaluation


Traceability ensures that implementation aligns with requirements.



------------------------------------------------------------
15. Documentation Requirements
------------------------------------------------------------

The system must maintain the following documentation:

Architecture
Data Flow
ADR (Architecture Decisions)
Evaluation Plan
Runbook
README


Documentation must explain:

what the system does
how the system works
why design decisions were made



------------------------------------------------------------
16. Production Readiness Criteria
------------------------------------------------------------

A production-grade system must satisfy:

modular architecture
structured logging
containerized deployment
automated tests
evaluation framework
graceful error handling
environment-based configuration
clear documentation



------------------------------------------------------------
Final Principle
------------------------------------------------------------

The goal of this doctrine is not just to produce working code.

The goal is to build systems that are:

maintainable
scalable
observable
explainable
production-ready
