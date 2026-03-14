# Skill Ontology Runtime Guide

This package owns runtime skill normalization and ontology adjacency logic.

## Module map

- `runtime.py`: `RuntimeSkillOntology` public class and scoring methods.
- `loader.py`: config YAML loading and parsing into runtime maps.
- `normalization.py`: token cleanup and dedupe helpers.
- `constants.py`: lexical normalization and version parsing patterns.
- `types.py`: `SkillNormalizationResult` contract.

## Public import contract

Keep using:

```python
from backend.services.skill_ontology import RuntimeSkillOntology, SkillNormalizationResult
```

This import remains stable even though internals are now modular.
