from __future__ import annotations

import re


LEGACY_LEXICAL_NORMALIZATION: dict[str, str] = {
    "mongo db": "mongodb",
    "mongo db-3.2": "mongodb",
    "ms office": "microsoft office",
}

VERSION_PATTERNS = [
    re.compile(r"^(sql server|ms sql server|microsoft sql server)\s+([0-9]{4}(?:\s*r2)?|[0-9]{4}r2)$"),
    re.compile(r"^(windows(?: server)?)\s+(xp|nt|7|8|10|[0-9]{4})$"),
    re.compile(r"^(oracle)\s+([0-9]+(?:\.[0-9]+)+|[0-9]{1,2}[a-z](?:r[0-9]+)?|[0-9]{1,2}[a-z]/[0-9]{1,2}[a-z])$"),
    re.compile(r"^(oracle)\s+([0-9]{1,2}[a-z]\s+rac)$"),
]
