from __future__ import annotations

from typing import Optional

from pymongo import MongoClient

from .settings import settings


_mongo_client: Optional[MongoClient] = None
_async_mongo_client: Optional["AsyncIOMotorClient"] = None


def _mongo_client_kwargs() -> dict:
    kwargs = {
        "maxPoolSize": settings.mongodb_max_pool_size,
        "minPoolSize": settings.mongodb_min_pool_size,
        "serverSelectionTimeoutMS": settings.mongodb_server_selection_timeout_ms,
        "connectTimeoutMS": settings.mongodb_connect_timeout_ms,
        "socketTimeoutMS": settings.mongodb_socket_timeout_ms,
        "retryWrites": settings.mongodb_retry_writes,
        "appname": settings.app_name,
    }
    if settings.mongodb_max_idle_time_ms is not None:
        kwargs["maxIdleTimeMS"] = settings.mongodb_max_idle_time_ms
    return kwargs


def get_mongo_client() -> MongoClient:
    """Singleton Mongo client."""
    global _mongo_client
    if _mongo_client is None:
        _mongo_client = MongoClient(settings.mongodb_uri, **_mongo_client_kwargs())
    return _mongo_client


def get_async_mongo_client() -> "AsyncIOMotorClient":
    """
    Singleton async Mongo client for FastAPI async handlers.

    Requires `motor` package installed.
    """
    global _async_mongo_client
    if _async_mongo_client is None:
        try:
            from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
        except ImportError as exc:
            raise RuntimeError("motor is not installed. Add 'motor' to requirements.") from exc
        _async_mongo_client = AsyncIOMotorClient(settings.mongodb_uri, **_mongo_client_kwargs())
    return _async_mongo_client


def get_db():
    client = get_mongo_client()
    return client[settings.mongodb_db]


def get_collection(name: str):
    db = get_db()
    return db[name]


def ensure_indexes() -> None:
    """Create basic indexes for candidates/jobs collections."""
    db = get_db()
    candidates = db["candidates"]
    jobs = db["jobs"]

    candidates.create_index("candidate_id", unique=True)
    candidates.create_index("category")
    candidates.create_index("parsed.seniority_level")

    jobs.create_index("job_id", unique=True)
    jobs.create_index("parsed_requirements.seniority")


def close_mongo_clients() -> None:
    global _mongo_client, _async_mongo_client
    if _mongo_client is not None:
        _mongo_client.close()
        _mongo_client = None
    if _async_mongo_client is not None:
        _async_mongo_client.close()
        _async_mongo_client = None
