# REPOSITORY STRUCTURE RULES

This document defines how the repository must be structured.

The goal is to maintain clarity, scalability,
and predictable project organization.

Location:
docs/governance/REPO_STRUCTURE_RULES.md


------------------------------------------------------------
1. High-Level Repository Layout
------------------------------------------------------------

resume-matching-pj/

config/
taxonomy configuration
alias mapping
normalization rules

data/
raw datasets
ingestion inputs

docs/

    adr/
    architecture decisions

    architecture/
    system diagrams

    data-flow/
    ingestion and retrieval flow

    governance/
    project governance documents

    ontology/
    ontology analysis and revisions

requirements/
problem statement
project requirements

scripts/
analysis tools
data preparation utilities

src/backend/

    api/
    FastAPI routers

    core/
    configuration
    database connections
    startup logic

    repositories/
    MongoDB query abstraction

    schemas/
    Pydantic models

    services/
    ingestion
    parsing
    matching
    scoring
    ontology

tests/
pytest test suite


------------------------------------------------------------
2. Source Code Ownership
------------------------------------------------------------

api/

HTTP interface only

Responsibilities

request validation
response formatting


services/

business logic
system orchestration


repositories/

database interaction
query abstraction


schemas/

Pydantic models
API validation
data transfer objects


core/

system configuration
startup initialization
external clients


------------------------------------------------------------
3. Document Organization
------------------------------------------------------------

docs/ contains all system documentation.

Key documents:

architecture diagrams
data flow diagrams
design decisions (ADR)
evaluation framework
governance documentation


Code documentation must not replace system documentation.


------------------------------------------------------------
4. Governance Documents
------------------------------------------------------------

docs/governance/

AGENT.md
PLAN.md
TRACEABILITY.md
DESIGN_DOCTRINE.md
ENGINEERING_DOCTRINE.md
CODING_STYLE_GUIDE.md
REPO_STRUCTURE_RULES.md


These documents define project governance
and engineering discipline.


------------------------------------------------------------
5. Tests Organization
------------------------------------------------------------

tests/

test_ingestion.py
test_matching.py
test_scoring.py


Each major service must have a corresponding test.


------------------------------------------------------------
6. Script Rules
------------------------------------------------------------

scripts/

used for:

ontology analysis
data preparation
migration utilities


Scripts must not contain core business logic.


------------------------------------------------------------
7. Configuration Rules
------------------------------------------------------------

config/

skill taxonomy
alias mapping
normalization rules


Configuration must remain separate from code.


------------------------------------------------------------
8. Principle

Repository structure should reflect system architecture.

Engineers must be able to understand the system
by looking at the folder layout alone.