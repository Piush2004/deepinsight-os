import os
from pydantic_settings import BaseSettings

# NOTE: no automatic .env loading here on purpose - this Settings instance is shared
# by both the running app AND the test suite (tests/conftest.py etc. import api.models
# -> api.core.config transitively). Auto-loading a local .env would silently change
# test behavior depending on what a developer happens to have on disk (confirmed: it
# broke tests/test_ollama_provider.py's "no fallback configured" assumption during
# this project's own dev-mode work). For local dev/demo, export the needed variables
# in your shell before starting uvicorn/the seed script instead - see
# docs/DEV_DEMO_MODE.md.

class Settings(BaseSettings):
    PROJECT_NAME: str = "DeepInsight OS"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # ENVIRONMENT / DEV-DEMO MODE
    # AUTH_MODE="demo" bypasses real Clerk JWT verification in api/core/security.py -
    # ONLY intended for local development/demo when Clerk credentials aren't available.
    # Hard-blocked whenever ENVIRONMENT=="production" (see get_current_user), so this
    # can never accidentally weaken real production authentication.
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    AUTH_MODE: str = os.getenv("AUTH_MODE", "clerk")
    # "pgvector" (default, needs real Postgres+pgvector) or "memory" (zero-dependency,
    # process-local, dev/demo only - see api/services/knowledge/vector_store.py).
    VECTOR_STORE_PROVIDER: str = os.getenv("VECTOR_STORE_PROVIDER", "pgvector")
    # Runs Celery tasks synchronously in-process, no Redis/worker needed - dev/demo
    # only, see api/core/celery_app.py.
    CELERY_EAGER: bool = os.getenv("CELERY_EAGER", "false").lower() == "true"
    # "dev" (default, the only implementation that exists) or "google_search_console"
    # (future work) - see api/services/seo/provider_factory.py.
    SEO_DATA_PROVIDER: str = os.getenv("SEO_DATA_PROVIDER", "dev")

    # DATABASE
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "db")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "deepinsight")
    
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite:///./test.db"
    )

    # CLERK
    CLERK_SECRET_KEY: str = os.getenv("CLERK_SECRET_KEY", "")
    CLERK_JWKS_URL: str = os.getenv("CLERK_JWKS_URL", "https://api.clerk.com/v1/jwks")
    CLERK_ISSUER: str = os.getenv("CLERK_ISSUER", "")
    CLERK_AUDIENCE: str = os.getenv("CLERK_AUDIENCE", "")
    
    # ENCRYPTION
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")

    # LLM (free/local-first, model-agnostic - see docs/PROJECT_RULES.md Rule 1)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "qwen2.5")
    OLLAMA_FALLBACK_MODEL: str = os.getenv("OLLAMA_FALLBACK_MODEL", "")
    OLLAMA_TIMEOUT_SECONDS: float = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    
settings = Settings()
