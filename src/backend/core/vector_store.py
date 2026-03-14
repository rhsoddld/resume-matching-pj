from __future__ import annotations

from dataclasses import dataclass
import logging
from threading import Lock
from typing import List, Sequence

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from .settings import settings

logger = logging.getLogger(__name__)


def _resolve_embedding_dim() -> int:
    model = settings.openai_embedding_model
    if model == "text-embedding-3-large":
        return 3072
    if model == "text-embedding-3-small":
        return 1536
    # Fallback to small-sized vectors for unknown models.
    return 1536


EMBEDDING_DIM = _resolve_embedding_dim()
_MILLISECONDS = 1_000
_MILVUS_ALIASES: list[str] = []
_MILVUS_ALIAS_LOCK = Lock()
_MILVUS_ALIAS_INDEX = 0
_LOADED_ALIASES: set[str] = set()


@dataclass
class CandidateEmbedding:
    candidate_id: str
    source_dataset: str
    category: str | None
    experience_years: float | None
    seniority_level: str | None
    vector: List[float]


def _milvus_connection_params() -> dict:
    params = {"uri": settings.milvus_uri}
    if settings.milvus_user and settings.milvus_password:
        params["user"] = settings.milvus_user
        params["password"] = settings.milvus_password
    # gRPC keepalive helps long-lived pooled channels stay healthy.
    params["keep_alive"] = True
    params["grpc.keepalive_time_ms"] = 30 * _MILLISECONDS
    params["grpc.keepalive_timeout_ms"] = 10 * _MILLISECONDS
    return params


def _initialize_connection_pool() -> None:
    global _MILVUS_ALIASES
    if _MILVUS_ALIASES:
        return

    pool_size = max(1, settings.milvus_pool_size)
    aliases = ["default"] + [f"milvus_pool_{i}" for i in range(1, pool_size)]
    params = _milvus_connection_params()

    for alias in aliases:
        if not connections.has_connection(alias):
            connections.connect(alias=alias, **params)
    _MILVUS_ALIASES = aliases
    logger.info("Milvus connection pool initialized aliases=%s", _MILVUS_ALIASES)


def _next_alias() -> str:
    global _MILVUS_ALIAS_INDEX
    _initialize_connection_pool()
    with _MILVUS_ALIAS_LOCK:
        alias = _MILVUS_ALIASES[_MILVUS_ALIAS_INDEX % len(_MILVUS_ALIASES)]
        _MILVUS_ALIAS_INDEX += 1
    return alias


def _get_or_create_collection(*, using: str | None = None) -> Collection:
    alias = using or _next_alias()
    _initialize_connection_pool()
    name = settings.milvus_collection
    if not utility.has_collection(name, using=alias):
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="candidate_id", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="source_dataset", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="category", dtype=DataType.VARCHAR, max_length=64),
            FieldSchema(name="experience_years", dtype=DataType.FLOAT),
            FieldSchema(name="seniority_level", dtype=DataType.VARCHAR, max_length=32),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        ]
        schema = CollectionSchema(fields, description="Candidate embeddings")
        collection = Collection(name=name, schema=schema, using=alias)
        collection.create_index(
            field_name="embedding",
            index_params={"index_type": "IVF_FLAT", "metric_type": "IP", "params": {"nlist": 1024}},
        )
    else:
        collection = Collection(name=name, using=alias)
        embedding_field = next((field for field in collection.schema.fields if field.name == "embedding"), None)
        existing_dim = None
        if embedding_field is not None:
            try:
                existing_dim = int(embedding_field.params.get("dim"))
            except (TypeError, ValueError, AttributeError):
                existing_dim = None
        if existing_dim is not None and existing_dim != EMBEDDING_DIM:
            raise ValueError(
                "Milvus collection embedding dim mismatch: "
                f"collection={existing_dim}, model={EMBEDDING_DIM} ({settings.openai_embedding_model})."
            )
    return collection


def _ensure_collection_loaded(collection: Collection, *, alias: str) -> None:
    if alias in _LOADED_ALIASES:
        return
    collection.load(timeout=float(settings.milvus_load_timeout_sec))
    _LOADED_ALIASES.add(alias)


def preload_collection() -> None:
    """
    Warm up Milvus collection at app startup to reduce first-query latency.
    """
    if not settings.milvus_preload_on_startup:
        return
    _initialize_connection_pool()
    for alias in _MILVUS_ALIASES:
        collection = _get_or_create_collection(using=alias)
        _ensure_collection_loaded(collection, alias=alias)
    logger.info("Milvus collection preloaded aliases=%s", _MILVUS_ALIASES)


def upsert_embeddings(items: Sequence[CandidateEmbedding]) -> None:
    if not items:
        return
    alias = _next_alias()
    collection = _get_or_create_collection(using=alias)
    # Some Milvus deployments require loaded collection even for delete expressions.
    _ensure_collection_loaded(collection, alias=alias)
    grouped_ids: dict[str, list[str]] = {}
    for item in items:
        grouped_ids.setdefault(item.source_dataset, []).append(item.candidate_id)

    for source_dataset, ids in grouped_ids.items():
        if not ids:
            continue
        escaped_ids = [cid.replace("\\", "\\\\").replace('"', '\\"') for cid in ids]
        quoted_ids = ", ".join(f'"{cid}"' for cid in escaped_ids)
        expr = f'source_dataset == "{source_dataset}" and candidate_id in [{quoted_ids}]'
        collection.delete(expr=expr)

    data = [
        [e.candidate_id for e in items],
        [e.source_dataset for e in items],
        [e.category or "" for e in items],
        [e.experience_years or 0.0 for e in items],
        [e.seniority_level or "" for e in items],
        [e.vector for e in items],
    ]
    # id is auto_id; don't provide it
    collection.insert(data=data)
    collection.flush()


def search_embeddings(
    query_vector: List[float],
    top_k: int = 10,
    category: str | None = None,
    min_experience_years: float | None = None,
) -> list[dict]:
    alias = _next_alias()
    collection = _get_or_create_collection(using=alias)
    _ensure_collection_loaded(collection, alias=alias)
    filters: list[str] = []
    if category:
        escaped_category = category.replace("\\", "\\\\").replace('"', '\\"')
        filters.append(f'category == "{escaped_category}"')
    if min_experience_years is not None:
        filters.append(f"experience_years >= {float(min_experience_years)}")
    expr = " and ".join(filters)
    results = collection.search(
        data=[query_vector],
        anns_field="embedding",
        param={"metric_type": "IP", "params": {"nprobe": 16}},
        limit=top_k,
        expr=expr or None,
        output_fields=["candidate_id", "source_dataset", "category", "experience_years", "seniority_level"],
    )
    hits = []
    for hit in results[0]:
        hits.append(
            {
                "candidate_id": hit.entity.get("candidate_id"),
                "source_dataset": hit.entity.get("source_dataset"),
                "category": hit.entity.get("category"),
                "experience_years": hit.entity.get("experience_years"),
                "seniority_level": hit.entity.get("seniority_level"),
                "score": float(hit.score),
            }
        )
    return hits
