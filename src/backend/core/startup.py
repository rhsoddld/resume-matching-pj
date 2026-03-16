from __future__ import annotations

import logging

from backend.core.database import ensure_indexes, get_mongo_client
from backend.core.vector_store import preload_collection


logger = logging.getLogger(__name__)


def warmup_infrastructure() -> None:
    """
    Run at application startup:
    - initialize MongoDB client and indexes
    - preload Milvus collection (if enabled)
    Does not raise: logs errors so the app can start and /api/health succeeds.
    Use /api/ready to see Mongo/Milvus status.
    """
    try:
        get_mongo_client()
        ensure_indexes()
    except Exception as exc:
        logger.exception("Mongo warmup failed (app will start; /api/ready will show degraded): %s", exc)

    try:
        preload_collection()
    except Exception as exc:
        logger.exception("Milvus preload failed (app will start; /api/ready will show degraded): %s", exc)

    logger.info("Startup warmup complete (Mongo + Milvus)")
