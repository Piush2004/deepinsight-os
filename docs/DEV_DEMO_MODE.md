# DeepInsight OS — Dev/Demo Mode

**Purpose:** run the full, real application end-to-end on a laptop with no Docker, no Postgres, no Clerk credentials, and no running Celery worker — using SQLite, an in-memory vector store, synchronous task execution, and a header-based auth bypass, all selected purely through configuration behind the existing interfaces. **Never used in production** — every piece here is explicitly gated and fails closed if `ENVIRONMENT=production`.

This is not a separate codebase or a set of mocks. It is the real `DocumentUploadService`, the real `ReportingAgent`/`ContentAgent`, the real `IntelligenceLayer`, the real Ollama calls, and the real approval workflow — running against swappable infrastructure, per `docs/PROJECT_RULES.md` Rule 6.

## What's swapped, and how

| Component | Production | Dev/demo | Switch |
|---|---|---|---|
| Database | PostgreSQL + pgvector | SQLite (`dev.db`) | `DATABASE_URL=sqlite:///./dev.db` |
| Vector store | `PgVectorStore` | `InMemoryVectorStore` (process-local, real cosine similarity) | `VECTOR_STORE_PROVIDER=memory` |
| Task execution | Celery worker + Redis | Synchronous, in-process | `CELERY_EAGER=true` |
| Authentication | Clerk JWT | Header-based demo bypass | `AUTH_MODE=demo` (backend) + `NEXT_PUBLIC_AUTH_MODE=demo` (frontend) |
| LLM | Ollama (unchanged either way) | Ollama (unchanged either way) | `OLLAMA_MODEL` must match a locally pulled tag — run `ollama list` |

Every one of these is read through `api/core/config.py`'s `Settings`, selected by a factory function (`get_vector_store()`, `AUTH_MODE` branch in `get_current_user()`) — no business logic anywhere knows or cares that it's running in this mode.

## Running it

**1. Backend** (from `apps/backend`, in a shell where you'll export these — not a `.env` file; see "Why no `.env` auto-loading" below):

```bash
export DATABASE_URL="sqlite:///./dev.db"
export AUTH_MODE=demo
export ENVIRONMENT=development
export VECTOR_STORE_PROVIDER=memory
export CELERY_EAGER=true
export OLLAMA_MODEL=qwen2.5:3b-instruct   # must match `ollama list` exactly on your machine
export OLLAMA_FALLBACK_MODEL=qwen2.5:3b-instruct

python -m scripts.seed_demo        # creates schema + demo users/clients/memberships
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**2. Populate documents + generate a report/content** (in a second shell, server already running):

```bash
python -m scripts.demo_http_walkthrough
```

This uploads real sample documents and generates a real report and real content draft **through the live server's own HTTP API** — not a separate script process. This matters: with `VECTOR_STORE_PROVIDER=memory`, the vector store is process-local, so anything that needs to land in the running server's in-memory store must go through that server's own requests, not a separate `python -m scripts.something` invocation talking directly to the database.

**3. Frontend** (`apps/frontend/.env.local`, auto-loaded by Next.js — this one *is* safe to commit-ignore-and-forget, unlike the backend's case):

```
NEXT_PUBLIC_AUTH_MODE=demo
NEXT_PUBLIC_API_URL=http://localhost:8000
```

```bash
npm run dev
```

Open `http://localhost:3000` — a yellow "Demo mode" banner appears on every page, with a dropdown to switch between the two seeded demo users (`demo-admin`, full access; `demo-manager`, member of only one seeded client — deliberately, to make tenant-isolation behavior demonstrable live in the browser).

## Why no `.env` auto-loading on the backend

An earlier version of this setup added `load_dotenv()` to `api/core/config.py` so a `.env` file would "just work" for local dev. This was reverted: `Settings` is a shared singleton imported by both the running app **and the test suite**, and a `.env` file with `CELERY_EAGER=true`/`OLLAMA_FALLBACK_MODEL=...` silently changed real test behavior and broke a real assertion in `tests/test_ollama_provider.py` the moment such a file existed on disk — a fragile, developer-machine-dependent failure mode. Export the variables in your shell instead, exactly as shown above.

## Known limitation: generation quality varies

With `LocalHashingEmbeddingProvider` (the zero-dependency fallback used when `sentence-transformers`/BGE-M3 isn't installed) and small demo documents, retrieval relevance is lower than real semantic search would produce — this can make the real, deterministic `EvaluationEngine` legitimately reject a generated report/content draft for low groundedness. **This is the system working correctly, not a bug** — the same quality gate that would reject a hallucinated report in production is active here too. Regenerating (the LLM is non-deterministic) or trying the larger `qwen2.5:7b-instruct-q4_K_M` model sometimes clears the bar; installing `sentence-transformers` for real BGE-M3 embeddings would improve this more reliably.

## Files

- `apps/backend/scripts/seed_demo.py` — DB-only seeding (users, clients, memberships). Safe to run before the server starts.
- `apps/backend/scripts/demo_http_walkthrough.py` — real HTTP walkthrough against a running server: uploads documents, queries knowledge, runs a live tenant-isolation attack, generates a report and content draft. Doubles as a live verification script.
- `apps/frontend/src/lib/demo-auth.ts` — frontend demo-mode/user-switcher state.
- `apps/frontend/src/components/ui/DemoBanner.tsx` — the always-visible mode indicator + user switcher.
