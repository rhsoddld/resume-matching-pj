from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import logging

from backend.core.startup import warmup_infrastructure
from backend.core.settings import settings
from backend.api import candidates, jobs

logging.basicConfig(level=settings.log_level)

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

app.include_router(candidates.router, prefix=settings.api_prefix)
app.include_router(jobs.router, prefix=settings.api_prefix)

@app.get("/api/health")
def health_endpoint():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
