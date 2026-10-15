import os
import sentry_sdk
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict
from prometheus_client import make_asgi_app
from sqlalchemy.orm import Session
from sqlalchemy import text
from api.database.session import get_db

# Initialize Sentry
if os.environ.get("SENTRY_DSN"):
    sentry_sdk.init(
        dsn=os.environ.get("SENTRY_DSN"),
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )

app = FastAPI(
    title="DeepInsight OS API",
    description="Backend API for DeepInsight OS",
    version="1.0.0"
)

# Add Prometheus metrics endpoint
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Should be configurable via env in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "ok", "service": "api"}

@app.get("/health/detailed")
def health_check_detailed(db: Session = Depends(get_db)) -> Dict[str, str]:
    try:
        # Check database connection
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return {"status": "error", "database": "disconnected", "details": str(e)}

@app.get("/version")
def version() -> Dict[str, str]:
    return {"version": "1.0.0"}

from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError
from api.core.exceptions import (
    validation_exception_handler,
    sqlalchemy_exception_handler,
    global_exception_handler,
)
from api.routers import clients, knowledge, reports, content, integrations, jobs, seo

app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

app.include_router(clients.router, prefix="/api/v1/clients", tags=["clients"])
app.include_router(knowledge.router, prefix="/api/v1")
app.include_router(knowledge.document_router, prefix="/api/v1")
app.include_router(reports.router, prefix="/api/v1")
app.include_router(content.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["integrations"])
app.include_router(jobs.router, prefix="/api/v1")
app.include_router(seo.router, prefix="/api/v1")
