# CODING STYLE GUIDE

This document defines coding style standards used across the project.

The goal is to ensure consistency, readability, and maintainability
of the codebase.

Location:
docs/governance/CODING_STYLE_GUIDE.md


------------------------------------------------------------
1. Python Style Standard
------------------------------------------------------------

This project follows:

PEP8
PEP257

General rules:

- 4 spaces indentation
- maximum line length: 100
- explicit imports preferred
- avoid wildcard imports


Example:

GOOD

from src.backend.services.matching_service import MatchingService


BAD

from services import *


------------------------------------------------------------
2. Naming Conventions
------------------------------------------------------------

Files

snake_case

Example

resume_parser.py
candidate_matcher.py
embedding_service.py


Classes

PascalCase

Example

ResumeParser
CandidateMatcher


Functions

snake_case
verb-based

Example

parse_resume()
generate_embedding()
match_candidates()


Variables

snake_case

Example

candidate_id
skill_list


Constants

UPPER_CASE

Example

MAX_RETRY
DEFAULT_TIMEOUT


------------------------------------------------------------
3. File Size Rule
------------------------------------------------------------

Files should remain small and focused.

Recommended limits:

500 lines maximum

If a file exceeds this size,
split into modules.


------------------------------------------------------------
4. Function Design Rule
------------------------------------------------------------

Functions must have a single responsibility.

Bad

process_resume()

Good

parse_resume()
generate_embedding()
store_candidate()
evaluate_candidate()


Recommended function length:

< 50 lines


------------------------------------------------------------
5. Logging Standard
------------------------------------------------------------

print() is forbidden.

All logging must use the logging module.

Example

logger.info(
    "candidate indexed",
    extra={
        "candidate_id": candidate_id
    }
)


Log Levels

DEBUG
INFO
WARNING
ERROR
CRITICAL


------------------------------------------------------------
6. Error Handling
------------------------------------------------------------

Never swallow exceptions.

Bad

try:
    run()
except:
    pass


Good

try:
    run()

except TimeoutError:

    logger.error("Timeout during embedding")

    raise


------------------------------------------------------------
7. Imports
------------------------------------------------------------

Imports should be grouped.

Order:

standard library
third party libraries
local modules


Example

import json
import logging

from fastapi import APIRouter

from src.backend.services.matching_service import MatchingService


------------------------------------------------------------
8. Type Hints
------------------------------------------------------------

Type hints are mandatory.

Example

def parse_resume(text: str) -> dict:


Example

def match_candidates(skills: list[str]) -> list[Candidate]:


------------------------------------------------------------
9. Schema Validation
------------------------------------------------------------

All API inputs must use Pydantic schemas.

Example

class JobRequest(BaseModel):

    description: str
    skills: list[str]
    experience_level: int


------------------------------------------------------------
10. Tests
------------------------------------------------------------

All services must be testable.

Tests must cover:

happy path
edge cases
error conditions


Example structure

tests/

test_ingestion.py
test_matching.py
test_scoring.py