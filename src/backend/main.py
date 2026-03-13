from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging

from backend.core.startup import warmup_infrastructure
from backend.core.exceptions import AppError
from backend.core.settings import settings
from backend.api import candidates, jobs

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    warmup_infrastructure()


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

@app.get("/api/health")
def health_endpoint():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
