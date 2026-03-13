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
    """
    get_mongo_client()
    ensure_indexes()
    preload_collection()
    logger.info("Startup warmup complete (Mongo + Milvus)")
