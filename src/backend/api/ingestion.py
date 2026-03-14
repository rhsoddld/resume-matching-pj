from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timezone
from threading import Lock
from time import monotonic
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Header, Request

from backend.core.exceptions import AppError
from backend.core.settings import settings
from backend.schemas.ingestion import IngestionRunRequest, IngestionRunResponse
from backend.services.ingest_resumes import iter_candidates, iter_candidates_from_mongo, run_ingestion

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


class InMemorySlidingWindowRateLimiter:
    def __init__(self, limit_per_minute: int):
        self.limit_per_minute = limit_per_minute
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key: str) -> bool:
        if self.limit_per_minute <= 0:
            return True

        now = monotonic()
        floor = now - 60.0

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < floor:
                bucket.popleft()
            if len(bucket) >= self.limit_per_minute:
                return False
            bucket.append(now)
            return True


_rate_limiter = InMemorySlidingWindowRateLimiter(settings.ingestion_rate_limit_per_minute)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _require_api_key(provided_key: str | None) -> None:
    expected_key = settings.ingestion_api_key
    if not expected_key:
        return
    if provided_key != expected_key:
        raise AppError(
            "Unauthorized ingestion request.",
            status_code=401,
            error_code="ingestion_unauthorized",
        )


def _enforce_rate_limit(request: Request) -> None:
    if settings.ingestion_rate_limit_per_minute <= 0:
        return

    _rate_limiter.limit_per_minute = settings.ingestion_rate_limit_per_minute
    client_key = request.client.host if request.client and request.client.host else "unknown"
    if not _rate_limiter.allow(client_key):
        raise AppError(
            "Ingestion rate limit exceeded. Please retry later.",
            status_code=429,
            error_code="ingestion_rate_limited",
        )


def _execute_ingestion(payload: IngestionRunRequest) -> None:
    write_mongo = payload.target in {"all", "mongo"}
    write_milvus = payload.target in {"all", "milvus"}

    if write_milvus and not write_mongo and payload.milvus_from_mongo:
        candidates = iter_candidates_from_mongo(
            payload.source,
            sneha_limit=payload.sneha_limit,
            suri_limit=payload.suri_limit,
        )
    else:
        candidates = iter_candidates(
            payload.source,
            sneha_limit=payload.sneha_limit,
            suri_limit=payload.suri_limit,
            csv_chunk_size=payload.csv_chunk_size,
            parser_mode=payload.parser_mode,
        )

    run_ingestion(
        candidates,
        write_mongo=write_mongo,
        write_milvus=write_milvus,
        batch_size=payload.batch_size,
        force_mongo_upsert=payload.force_mongo_upsert,
        force_reembed=payload.force_reembed,
        dry_run=payload.dry_run,
    )


@router.post("/resumes", response_model=IngestionRunResponse)
def ingest_resumes_endpoint(
    payload: IngestionRunRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
):
    _require_api_key(x_api_key)
    _enforce_rate_limit(request)

    request_id = uuid4()
    accepted_at = _utcnow()

    if payload.async_mode:
        if not settings.ingestion_allow_async:
            raise AppError(
                "Async ingestion is disabled by server policy.",
                status_code=400,
                error_code="ingestion_async_disabled",
            )

        background_tasks.add_task(_execute_ingestion, payload)
        return IngestionRunResponse(
            request_id=request_id,
            status="accepted",
            message="Ingestion scheduled.",
            source=payload.source,
            target=payload.target,
            dry_run=payload.dry_run,
            accepted_at=accepted_at,
            completed_at=None,
        )

    _execute_ingestion(payload)
    return IngestionRunResponse(
        request_id=request_id,
        status="completed",
        message="Ingestion finished successfully.",
        source=payload.source,
        target=payload.target,
        dry_run=payload.dry_run,
        accepted_at=accepted_at,
        completed_at=_utcnow(),
    )
