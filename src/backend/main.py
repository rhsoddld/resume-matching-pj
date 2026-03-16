from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from backend.core.startup import warmup_infrastructure
from backend.core.exceptions import AppError
from backend.core.database import get_mongo_client
from backend.core.settings import settings
from backend.api import candidates, ingestion, jobs, feedback
from ops.logging import configure_logging, get_logger
from ops.middleware import RequestIdMiddleware, APILoggingMiddleware
from pymilvus import connections, utility

configure_logging(log_level=settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    warmup_infrastructure()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(APILoggingMiddleware)  # innermost: log each API request to MongoDB
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIdMiddleware)  # outermost: set request_id for logging


@app.exception_handler(AppError)
def app_error_handler(_: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_code": exc.error_code},
    )


@app.exception_handler(Exception)
def unhandled_exception_handler(_: Request, exc: Exception):
    logger.exception("Unhandled exception in request processing.", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error.", "error_code": "internal_server_error"},
    )

app.include_router(candidates.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)
app.include_router(ingestion.router, prefix=settings.api_prefix)
app.include_router(feedback.router, prefix=settings.api_prefix)


def _check_mongo_ready() -> tuple[bool, str | None]:
    try:
        get_mongo_client().admin.command("ping")
        return True, None
    except Exception as exc:
        logger.exception("Mongo readiness check failed.", exc_info=exc)
        return False, str(exc)


def _check_milvus_ready() -> tuple[bool, str | None]:
    try:
        alias = "milvus_ready_probe"
        params = {"uri": settings.milvus_uri}
        if settings.milvus_user and settings.milvus_password:
            params["user"] = settings.milvus_user
            params["password"] = settings.milvus_password
        if not connections.has_connection(alias):
            connections.connect(alias=alias, **params)
        utility.list_collections(using=alias)
        return True, None
    except Exception as exc:
        logger.exception("Milvus readiness check failed.", exc_info=exc)
        return False, str(exc)


@app.get("/api/health")
def health_endpoint():
    return {"status": "ok"}


@app.get("/api/ready")
def ready_endpoint():
    mongo_ok, mongo_error = _check_mongo_ready()
    milvus_ok, milvus_error = _check_milvus_ready()
    checks = {
        "mongo": {"ok": mongo_ok},
        "milvus": {"ok": milvus_ok},
    }
    if mongo_error:
        checks["mongo"]["error"] = mongo_error
    if milvus_error:
        checks["milvus"]["error"] = milvus_error
    is_ready = mongo_ok and milvus_ok
    status_code = 200 if is_ready else 503
    status = "ready" if is_ready else "degraded"
    return JSONResponse(status_code=status_code, content={"status": status, "checks": checks})


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
