# DeepInsight OS — Implementation Audit

> **Status as of 2026-08-15: the findings below (original audit, 2026-08-14) have
> largely been repaired.** See [**Repair Log**](#repair-log-2026-08-15) at the bottom of
> this document for what changed, file by file, with before/after status per finding.
> Sections above the Repair Log are preserved as the original, unmodified audit — do
> not edit them; they're the historical record the repair log is measured against. For
> the current, forward-looking state of every component, see
> `docs/IMPLEMENTATION_STATUS.md`.

**Auditor:** Claude Code (takeover audit, independent of prior agent's completion reports)
**Date:** 2026-08-14
**Method:** Full static read of backend (`apps/backend`) and frontend (`apps/frontend`) source, models, migrations, tests, CI config, and Docker/Compose config, cross-checked against the project's own `docs/PROJECT_RULES.md`, `docs/ROADMAP.md`, `docs/PHASE_1_DESIGN.md`, and `Phase4_Architecture.md`. Findings below were produced by 8 independent domain audits and then spot-verified directly (see "Independently re-verified" notes).

**Environment limitation — read first:** This machine has **no Docker, no local PostgreSQL, and no local Redis** (confirmed via `docker --version`, `where.exe psql/redis-server` — none found). `docker compose up --build`, live pgvector retrieval, live Celery execution, and live Ollama inference **could not be run or observed**, only read. Everywhere "runtime behavior" is claimed below, it is inferred from code, not observed live. This is a hard gap the user must close (install Docker Desktop, or hand this environment a way to run containers) before P0 items can be closed out with actual runtime verification rather than static analysis.

Two things **were** independently executed directly, not just read:
- `python -c "import api.models"` → **fails**, `ImportError: cannot import name 'KnowledgeDocument'` (confirms an agent finding).
- `npm run build` (Next.js production build) → **fails outright** on `apps/frontend/src/app/(dashboard)/settings/integrations/page.tsx`: imports `Linkedin` from `lucide-react@1.27.0`, which doesn't export that name. **The frontend does not currently produce a production build**, independent of any Docker issue.

---

## Executive summary

The prior agent's phase-completion claims are **not supported by the code**. What exists is a well-organized skeleton: real interfaces, real-looking models, a genuinely working `BaseAgent` lifecycle, and a few isolated pieces of real logic (brand-voice term matching, the recursive chunker, the pgvector SQL, Clerk JWT signature verification). But **almost none of it is wired together**. Every API router for the four claimed feature phases (Knowledge, Reporting, Content, Integrations-partially) either returns hardcoded literals and never touches the database, or — for `integrations.py` — has no authentication at all. The frontend has zero backend integration (no `fetch`/API client exists anywhere in `src`) and does not build. CI's test step is a comment plus `echo "Tests placeholder"` — no test has ever actually run in CI. The one true P0 security finding beyond auth/tenancy is confirmed plaintext storage of OAuth tokens.

**Nothing in this repository should be described as "production-ready" today.**

---

## Status by area

| Area | Status | One-line reason |
|---|---|---|
| Architecture (interfaces, layering) | **PARTIAL** | Interfaces/abstractions are real and well-designed; almost nothing concrete is wired to them |
| Authentication | **PARTIAL** | Clerk JWT signature verification is real; issuer/audience checks disabled; `integrations.py` router has no auth at all |
| RBAC | **PARTIAL** | `require_role()` is genuinely implemented; but it's the only access-control layer — no resource/tenant-ownership check anywhere |
| Multi-tenancy (Rule 2) | **BROKEN** | No user↔client membership table exists at all; `client_id` is a caller-supplied, unverified param on every endpoint that accepts one (IDOR) |
| Knowledge Base (Phase 1) | **BROKEN** | Upload/list/query endpoints are 100% hardcoded stubs; pipeline internals exist but are never invoked; retrieval/RAG has zero implementation |
| Reporting Agent (Phase 2) | **BROKEN** | `/reports/*` endpoints never call the agent or touch the DB; Celery task body is `pass` |
| Intelligence Layer (Phase 2.5) | **MOCKED** | Rule Engine has no trend/%-change math at all; Confidence Score and Evaluation Engine are hardcoded constants; not called by any agent |
| Content Platform (Phase 3) | **MOCKED / BROKEN** | `ContentAgent` + brand-voice rejection work in isolation (real, tested) but are unreachable — `/content/*` endpoints are stubs; `finalize()` never persists |
| Phase 4 integrations (GA4/GSC) | **MOCKED** | OAuth, sync, and metrics are all hardcoded fixtures; confirmed plaintext token storage (P0); Celery queue routing doesn't match the worker's consumed queues |
| Celery / background jobs | **PARTIAL** | Broker/backend config is real; the one working task (`sync_integration_data`) has real DB writes; report task is a stub; no idempotency/dedup; orphaned "running" rows on crash |
| Database models & migrations | **BROKEN** | `api/models/__init__.py` imports non-existent class names → package fails to import → `alembic` itself can't run; migrations cover well under half the ORM's tables; `integrations` table columns don't match the model |
| Frontend UI | **MOCKED, does not build** | Every data page renders hardcoded arrays; no API client exists anywhere; production build fails on a bad icon import |
| Tests | **MOCKED, not run by CI** | Existing tests exercise real orchestration in places but assert against hardcoded stub output; zero tenant-isolation tests; zero real-DB tests; CI's pytest step is commented out |
| Production infra (Docker/Sentry/Prometheus) | **UNVERIFIED (Docker unavailable here)** | Compose file looks structurally correct for Postgres/Redis/API/worker/frontend; Sentry/Prometheus are SDK-wired in `main.py` but have no dedicated scrape/dashboard infra in compose |

---

## Detailed findings

### 1. Authentication & RBAC — PARTIAL
*(Full findings: backend security audit agent, independently spot-checked)*

- `api/core/security.py` does real RS256 signature verification against Clerk's live JWKS. **Real.**
- Same file explicitly disables issuer/audience checks: `options={"verify_aud": False, "verify_iss": False}` with a comment `# In production, check audience and issuer`. **Not production-safe as shipped.**
- `require_role()` genuinely loads the `User` row and checks `role in allowed_roles`. **Real**, but it is the *only* access-control primitive in the system — there is no concept of "is this user allowed to touch this specific client's data."
- `apps/backend/api/routers/integrations.py` — **every endpoint has zero auth dependency.** Anyone who can reach the API can list/connect/sync/disconnect any client's integrations unauthenticated.
- `apps/backend/api/main.py`: `CORSMiddleware(allow_origins=["*"], allow_credentials=True)` — permissive dev config left in place.

### 2. Multi-tenancy (Rule 2) — BROKEN
The project's own non-negotiable rule ("every operation must include client_id, no shortcuts") is not achievable in the current schema:
- `api/models/user.py` has no `client_id` and there is **no membership/join table anywhere** mapping a user to the client(s) they're allowed to see.
- Every router that accepts `client_id` (as query/body param) trusts it from the caller with no ownership check — this is IDOR by construction, not an edge case.
- `clients.py`'s `get_client` has no ownership filter at all — any authenticated user, regardless of role, can fetch any client by UUID.
- Roughly a third of ORM tables (`document_versions`, `document_chunks`, `report_versions`, `content_versions`, `content_comments`, `content_scores`, `execution_metrics`, etc.) carry no direct `client_id` column and depend on multi-level joins back to a tenant-scoped ancestor — which is only safe if every query actually performs that join, and today those queries mostly don't exist because the routers are stubs.
- **No test in the repository verifies tenant isolation.** This was explicitly checked and confirmed absent.

### 3. Knowledge Base (Phase 1) — BROKEN
Design intent: upload → validate → extract → chunk → embed → store (pgvector) → retrieve with citations.

- `POST /documents` and every other knowledge endpoint return hardcoded literals (`{"documents": []}`, a canned upload-success message) and never call `DocumentUploadService`, `PgVectorStore`, or any pipeline class. **The claimed pipeline is unreachable from the API.**
- Pipeline internals, graded independently since they're dead code today:
  - Text extraction: real for TXT/Markdown/PDF (`pypdf`); no DOCX loader.
  - Chunking: real recursive-splitter algorithm; `chunk_overlap` parameter is accepted but never used (author's own comment: "without overlap logic for brevity in scaffolding").
  - Embedding: real `sentence-transformers` BGE-M3 call — but `sentence-transformers` doesn't appear in `requirements.txt`, so this would likely `ImportError` at runtime even if reached.
  - Storage: `StorageService.store()` body is `pass` — chunks and embeddings are computed and then discarded.
  - Vector store (`vector_store.py`): genuinely well-built parameterized pgvector cosine-distance SQL — but it creates its own table at runtime via `CREATE TABLE IF NOT EXISTS` rather than through Alembic, so it lives entirely outside the migration system.
  - Retrieval/RAG: **does not exist.** `Retriever` and `KnowledgeQueryService` are abstract interfaces with zero concrete implementations anywhere in the codebase. There is no similarity-search-to-prompt path and no citation-assembly logic.
- Virus scanning: absent, but the project's own design doc already labels this an intentional placeholder — not a regression.

### 4. Reporting Agent (Phase 2) & Intelligence Layer (Phase 2.5) — BROKEN / MOCKED
- `BaseAgent` (`api/core/agent/base.py`) is the one genuinely solid piece: it really does enforce `initialize → validate → gather_context → execute → validate_output → request_approval → finalize → audit`, with a passing unit test.
- `POST /reports/generate` never invokes the agent, never enqueues a Celery task — it returns a canned `{"status": "processing"}` dict. All other report endpoints (`approve`, `reject`, `comment`, `history`) ignore the injected `db: Session` entirely.
- `_run_report_logic` in `api/core/tasks.py` is a `pass` stub behind a `@retry` decorator.
- Rule Engine: **no percentage-change/trend math exists anywhere in the codebase** — confirmed by grep across the intelligence services. The only logic present is two static threshold checks on the *current* period, with hardcoded confidence values (95, 90) that are literals, not computed. The audit scenario in the takeover brief ("CTR 2%→4% should read +100%, not +2%") is moot: there is no calculation to be wrong.
- Evaluation Engine: hardcoded constant scores (`groundedness: 95, completeness: 88, ...`) returned regardless of input — the source comment admits *"we simulate deterministic heuristics."* It is also never called by `ReportingAgent.validate_output()`.
- Citation validation only checks that a citations list is non-empty, not that citations correspond to retrieved content — fabricated citations would pass undetected (moot in practice today since retrieval doesn't exist, per §3).

### 5. Content Intelligence Platform (Phase 3) — MOCKED / BROKEN
- `ContentAgent` and its brand-voice rejection path are genuinely functional **in isolation** and covered by a real passing test (`ValueError: Forbidden term detected: 'badword'`).
- Every `/content/*` endpoint is a stub identical in pattern to the reporting router — none call `ContentAgent`, none touch the DB.
- `ContentAgent.finalize()` is `pass` — even if invoked directly, nothing persists to `Content`/`ContentVersion`/`ContentScore`.
- `ContentQualityEngine.score_content()` is a hardcoded stub (`# We simulate scoring here`) returning ~89 regardless of input — the `>= 80` quality gate can never actually reject anything.
- Only one prompt template exists (`blog.md`) — no LinkedIn/Email/Social templates despite those being claimed content types.
- Frontend `dashboard/content/page.tsx`: zero `fetch`/`useEffect`; hardcoded content list, fake author "Editor AI", fake "2 hours ago" timestamp; Generate/Approve/Reject/Comment buttons have **no onClick handlers at all**.

### 6. Phase 4 — GA4/GSC Integrations — MOCKED (P0 security issue confirmed)
The project's own `Phase4_Architecture.md` self-admits OAuth is mocked and token encryption is missing. Verification confirmed this and found more:
- **P0 — OAuth tokens are stored in plaintext.** `ConnectorToken.access_token`/`refresh_token` are plain `String` columns; connectors write raw strings directly. The codebase already has a working `EncryptedString`/`encryption_service` pattern used for `Client` secrets — it was simply not applied here. This is a skipped step, not a knowledge gap.
- `authenticate()` inserts literal strings `"mock_ga4_access_token"` / `"mock_gsc_access_token"`; no Google API client library is a dependency anywhere.
- `sync()` returns hardcoded fixture dicts (fake sessions/conversions/revenue, a literal query `"joseph studios marketing"`); `normalize()` itself is real transformation logic, just never fed real input.
- `refresh_token()` returns a hardcoded string and never persists it — refreshed tokens are silently discarded.
- `ConnectorToken.integration_id` is unique, but `authenticate()` always inserts — a second OAuth connect for the same integration will raise `IntegrityError`.
- **New finding, not in the prior doc:** Celery queue routing config (`celery_app.py`) routes on task-name prefixes that don't match the actual registered task names (`api.core.tasks.process_report_generation`, `api.core.tasks.sync_integration_data`). Both fall through to Celery's default `"celery"` queue, which the worker (per `docker-compose.yml`, consuming only `default,heavy_processing`) never listens to. **As configured, dispatched sync tasks would hang forever and never execute.**
- No idempotency/dedup constraint on `NormalizedMetric` — calling `/sync` twice duplicates every row.
- `_trigger_intelligence_layer()` is a log line, confirmed as stated in the prior doc.
- `ConnectorLog` model exists but is never written to anywhere — dead schema.

### 7. Database models & migrations — BROKEN
- `api/models/__init__.py` imports `KnowledgeDocument` and `ContentAsset`, neither of which exist (`knowledge.py` defines `Document`, `content.py` defines `Content`). **Confirmed by direct execution: `import api.models` raises `ImportError` today.** Since `alembic/env.py` imports from `api.models`, **`alembic upgrade head` cannot currently run.** The same wrong name is used live in `api/core/tasks.py`'s `_ingest_to_knowledge_layer`, so that Celery code path would also crash on first execution.
- Only 2 migrations exist, covering roughly 9 of 27 ORM-defined tables. **19 tables — the entire Content and Reporting domains, and 5 of 6 Integrations tables — have no migration at all.** A fresh `alembic upgrade head` today would not produce a database the application can use.
- The one migrated `integrations` table has columns (`platform`, `credentials`) that don't match the current model (`provider`, `status`) — any query against `Integration.provider` fails against a freshly migrated DB.
- The pgvector shadow table (`document_vectors`) exists only as runtime `CREATE TABLE IF NOT EXISTS` SQL, entirely outside Alembic.
- No SQL-injection risk found — all raw SQL is parameterized.

### 8. Frontend — MOCKED, does not build
- **Confirmed directly: `npm run build` fails.** `settings/integrations/page.tsx` imports `Linkedin` from `lucide-react@1.27.0`, which doesn't export that name.
- No API client exists anywhere in `src` — zero `fetch`/`axios` calls in the entire frontend; no `axios`/`swr`/`react-query` dependency is even installed. `NEXT_PUBLIC_API_URL` is declared in `.env.example` but never read by any code.
- Every data-bearing page (Executive Command Center, Clients list, Client detail, Settings→Integrations, Content, Reports) renders hardcoded literal arrays or objects. `clients/[clientId]/page.tsx` doesn't even read the `clientId` route param — every client detail page shows the same hardcoded "Acme Corp."
- Routing bug: `dashboard/reports` and `dashboard/content` are plain segments outside the `(dashboard)` route group, so they render with **no sidebar/header** — losing all navigation chrome on two of five primary nav destinations, which the Sidebar/CommandPalette components deliberately link to.
- Dead link: Command Center links to `/agents`, which doesn't exist anywhere in the route tree.
- Numerous buttons (New Client, Configure, Generate Draft, Approve Draft, New Report, View) have no `onClick` handler.
- Clerk auth middleware (`middleware.ts`) is the one genuinely real piece — it does gate all non-public routes correctly.

### 9. Tests & CI — MOCKED, never actually run
- **`.github/workflows/ci.yml` line 24 has the real pytest invocation commented out**, replaced with `echo "Tests placeholder"`. No backend test has ever executed in CI, regardless of whether it would pass.
- Content/reporting tests do exercise real `BaseAgent` orchestration and real brand-voice validation, but assert against a hardcoded quality-score stub, making some assertions tautological.
- Knowledge tests are two auth-smoke-checks (401/403 on missing token) plus one constructor no-op that instantiates the pipeline with `db=None` and asserts only `is not None`.
- **Zero tests touch a real or in-memory database.** Zero tenant-isolation tests. Zero cross-role authorization tests. Zero positive authenticated-flow tests.
- A latent Python-version landmine was found: two test files reference `UUID` in a type annotation without importing it. This is masked on Python 3.14 (deferred annotation evaluation) but would very likely cause a collection-time `NameError` on Python 3.11 — the exact version CI's `setup-python` step pins.
- The backend `.venv` present in the repo has drifted from `requirements.txt` — installed versions (`fastapi 0.140.13`, `alembic 1.18.5`, etc.) don't match the pins (`fastapi==0.110.0`, `alembic==1.13.1`); reinstalling exact pins failed here (`pydantic-core` has no prebuilt wheel for the installed Python 3.14, and building from source failed). The dev environment is not currently reproducible from `requirements.txt` as committed.

### 10. Repository hygiene (new observations, not in the original phase claims)
- `D:\Projects\Joseph Project\DeepInsightOS` itself is **not a git repository** (`git status` → "not a git repository"), despite containing a `.github/workflows` CI config that presumes one. `apps/frontend` has its own separate nested `.git` — an inconsistent, partially-versioned monorepo.
- Production infra claims (Sentry, Prometheus) are only SDK-level: `main.py` conditionally initializes Sentry if `SENTRY_DSN` is set and mounts a Prometheus `/metrics` ASGI app — both real code — but `docker-compose.yml` has no Prometheus/Grafana service and no documented Sentry project, so "Sentry + Prometheus observability" is infrastructure-optimistic rather than a working monitoring stack today.

---

## What could not be verified in this environment

Docker, PostgreSQL, and Redis are unavailable here, so the following from the original audit brief were **not** exercised live and remain UNVERIFIED beyond static reading:
- `docker compose up --build` end-to-end boot, health checks, container-to-container networking
- Live Alembic `upgrade head` / `downgrade -1` / `upgrade head` cycle against real Postgres+pgvector
- Live Celery worker execution, retry-on-kill behavior, queue consumption
- Live Ollama LLM calls (availability, timeout, malformed/empty output, fallback behavior)
- Actual multi-tenant data leakage under live concurrent requests (the schema/code-level IDOR gaps above make this predictable, but it wasn't observed with real HTTP calls)

These should be run for real — on a machine with Docker — before anything here is called production-ready, per the original brief's own stop conditions.

---

## Priority ranking of what to fix

**P0 (blocks everything else):**
1. Fix `api/models/__init__.py` (`KnowledgeDocument`→`Document`, `ContentAsset`→`Content`) — the package doesn't import today.
2. Fix `_ingest_to_knowledge_layer` in `tasks.py` to match real model fields (same root cause).
3. Write the missing Alembic migrations for the 19 un-migrated tables; fix the `integrations` table column drift.
4. Encrypt `ConnectorToken.access_token`/`refresh_token` at rest using the existing `encryption_service`.
5. Add a user↔client membership model and enforce it on every endpoint that currently trusts a caller-supplied `client_id`; add auth to `integrations.py`.
6. Fix the frontend production build (`lucide-react` import).
7. Re-enable real `pytest` execution in CI.

**P1 (core functionality claimed but non-functional):**
8. Wire the Knowledge/Reporting/Content routers to their actual services/agents instead of stub returns.
9. Implement retrieval/RAG (currently doesn't exist at all).
10. Fix Celery queue routing so dispatched tasks are actually consumed.
11. Build a real Rule Engine (trend/%-change math) and real Evaluation/Confidence scoring instead of hardcoded constants.
12. Add tenant-isolation and cross-role authorization tests.

**P2/P3:** frontend routing-group fix (reports/content losing chrome), dead links, missing onClick handlers, CORS hardening, idempotency constraints — deferred until P0/P1 are closed, per the brief's own stop conditions.

---

## Repair Log (2026-08-15)

**Method note:** every fix below was verified by running it, not just reading it —
`python -c "import api.models"` / `from api.main import app`, the full `pytest`
suite (grew from 8 tests to 71 passing + 9 correctly-skipped), `ruff check .`,
`npm run build` / `npm run lint` / `npm run typecheck`, and a live `npm run dev`
smoke test. Two things remain genuinely unverified at runtime because they require
credentials this environment doesn't have — flagged explicitly at the end of this
log, not glossed over.

### Finding 1 — Authentication & RBAC (was PARTIAL)
- **Root cause:** `verify_token()` explicitly set `verify_aud`/`verify_iss` to `False`; `integrations.py` had no `Depends(require_role(...))` on any route at all.
- **Fix:** Added `CLERK_AUDIENCE` setting; `verify_token()` now fails closed (500) if `CLERK_ISSUER`/`CLERK_AUDIENCE` aren't configured, and enforces both via python-jose. Added JWKS key-rotation handling (refetch once on unknown `kid`). Added `require_role(...)` + `assert_client_access(...)` to every `integrations.py` endpoint.
- **Files:** `api/core/security.py`, `api/core/config.py`, `api/routers/integrations.py`, `.env.example`.
- **Tests:** `tests/test_security.py` (9 tests, real RS256 keypair generated per-run — valid/no-token/tampered/expired/wrong-issuer/wrong-audience/unknown-kid/missing-config-fails-closed).
- **Status: FIXED, VERIFIED** (real signature math + real rejection paths, not mocked).

### Finding 2 — Multi-tenancy / Rule 2 (was BROKEN)
- **Root cause:** No user↔client membership concept existed; every router trusted a caller-supplied `client_id`.
- **Fix:** New `ClientMembership` model (`user_id`, `client_id`, unique pair). New `api/core/security.py` primitives: `user_has_client_access()`, `assert_client_access()` (404s, not 403s, to avoid confirming cross-tenant resource existence), `require_client_access()` dependency factory. Applied to **every** client-scoped endpoint across `clients.py`, `integrations.py`, `knowledge.py`, `reports.py`, `content.py` — either via the dependency (list/history endpoints) or by loading the resource first and checking its *own* `client_id` (detail/mutate endpoints), never trusting a caller-supplied id for ownership. Admin role bypasses membership (grants all-client access) by design. `ClientService.create_client()` now auto-grants the creating non-Admin user membership on their new client.
- **Files:** `api/models/membership.py` (new), `api/core/security.py`, `api/repositories/client_repository.py`, `api/services/client_service.py`, `api/routers/{clients,integrations,knowledge,reports,content}.py`.
- **Tests:** `tests/test_tenant_access.py` (8 tests: admin bypass, membership required, malformed-id handling, 404-not-403 behavior).
- **Status: FIXED, VERIFIED** (unit-level, real logic). **UNVERIFIED at HTTP/DB level** — needs Postgres to run a live cross-client IDOR attempt end-to-end (see "Still blocked" below).

### Finding 3 — Knowledge Base / Phase 1 (was BROKEN)
- **Root cause:** Every `/documents`/`/knowledge` endpoint returned hardcoded literals; `StorageService.store()` was `pass`; no `Retriever`/`KnowledgeQueryService` implementation existed at all.
- **Fix:** Real end-to-end pipeline wired into `knowledge.py`: upload → `ValidationService` (real size/mime checks, was `pass`) → extraction (existing loaders) → chunking → embedding → `StorageService` (now writes real `DocumentChunk`/`EmbeddingRecord`/`KnowledgeMetadata` rows + calls the real `PgVectorStore`) → `VerificationService` (now marks real status, was `pass`). Added checksum-based dedup/versioning (re-uploading identical content creates a new `DocumentVersion`, not a duplicate `Document`). Built the entirely-missing retrieval layer: `PgVectorRetriever` + `RagKnowledgeQueryService` (real embed → similarity search → resolve chunk text/citations, never fabricates an answer — returns `grounded: false` with no sources on a miss). Added `LocalHashingEmbeddingProvider` as a genuine zero-dependency fallback (real feature-hashing algorithm, not a mock) for when `sentence-transformers`/BGE-M3 isn't installed, with graceful `get_embedding_provider()` selection + a loud warning log.
- **Files:** `api/services/knowledge/{pipeline,embeddings,retrieval,loaders}.py` (retrieval.py new), `api/routers/knowledge.py` (rewritten).
- **Tests:** `tests/test_knowledge_e2e.py` (4 Postgres-gated tests: real chunk/embedding persistence, dedup-creates-new-version, grounded retrieval returns real citations, tenant-isolated retrieval — Client B's query never surfaces Client A's content).
- **Status: FIXED, code-complete and unit-verified. UNVERIFIED at the database level** — these are exactly the tests blocked on Postgres+pgvector access (see below); they're written and will run the moment that's available.

### Finding 4 — Reporting Agent / Intelligence Layer (was BROKEN / MOCKED)
- **Root cause:** `/reports/generate` never called the agent; Rule Engine had no trend math; Evaluation Engine and Confidence Score were hardcoded constants; Intelligence Layer was never invoked by any agent.
- **Fix:** Built `RuleEngine.calculate_percentage_change()` — the exact spec case (CTR 2%→4%) now correctly returns `+100.0`, not `+2`. Added real trend signals for 7 metrics with a real significance threshold and a margin-based (not hardcoded) confidence score. Rewrote `EvaluationEngine` with 6 genuinely computed, dependency-free heuristics (Flesch readability, lexical-overlap groundedness, numeric-hallucination detection, etc. — see `api/services/intelligence/text_heuristics.py`), with a blended pass/fail gate (not "every metric ≥80", which would reject legitimate paraphrasing) plus two hard floors (groundedness floor, hallucination ceiling). Wired `IntelligenceLayer` into `ReportingAgent.gather_context()`/`validate_output()` for the first time — it was previously never called. `ReportingAgent`/`ContentAgent` now accept a `db` session and `finalize()` actually persists `Report`/`ReportVersion`/`ApprovalRequest` (and `Content`/`ContentVersion`/`ContentScore`/`ContentApprovalRequest`) rows — both were `pass` before. New `ReportComment` model (parity with `ContentComment`, which already existed). `/reports/generate` now dispatches a real Celery task that builds and runs the real agent with real `OllamaProvider`/`RagKnowledgeQueryService`/`IntelligenceLayer` collaborators; all other `/reports/*` endpoints do real DB reads/writes (approve/reject/comment/history), not canned responses.
- **Files:** `api/services/intelligence/{rule_engine,insight_engine,evaluation_engine,engine,text_heuristics}.py` (text_heuristics.py new), `api/core/agent/reporting_agent.py`, `api/core/tasks.py`, `api/routers/reports.py`, `api/models/reporting.py`, `prompts/reporting/executive_summary.md`.
- **Tests:** `tests/test_intelligence_layer.py` (12 tests incl. the exact spec scenario), `tests/test_reporting.py` (rewritten — real `IntelligenceLayer` instance, not mocked, plus a new low-quality-rejection test), `tests/test_reporting_e2e.py` (2 Postgres-gated tests: real Report/ReportVersion/ApprovalRequest persistence, tenant-scoped).
- **Status: FIXED, VERIFIED** (math/heuristics are unit-tested with real assertions). Persistence layer is **code-complete, UNVERIFIED at the database level** pending Postgres.

### Finding 5 — Content Intelligence Platform (was MOCKED / BROKEN)
- **Root cause:** `/content/*` endpoints were stubs; `ContentAgent.finalize()` was `pass`; `ContentQualityEngine` returned hardcoded scores regardless of input.
- **Fix:** `ContentQualityEngine` rewritten on the same real `text_heuristics` module as the Reporting Agent's Evaluation Engine (originality via n-gram overlap, real grammar/tone/readability/brand-consistency checks) — no more hardcoded ~89. `ContentAgent.finalize()` now persists real `Content`/`ContentVersion`/`ContentScore`/`ContentApprovalRequest` rows, and supports editing an existing `Content` (creates a new version) vs. creating new. `/content/*` router rewritten identically to `/reports/*` — real Celery dispatch, real approve/reject/comment/calendar/history against the DB. Fixed a pre-existing role-name typo (`"Copywriter"` in the router vs. `"Content Writer"` used everywhere else in the codebase — would have silently locked out the correct role).
- **Files:** `api/core/agent/content_agent.py`, `api/services/validation/content_quality.py`, `api/routers/content.py`, `api/core/tasks.py`.
- **Tests:** `tests/test_content.py` (rewritten with realistic-length mock output so the real quality gate is genuinely exercised, not trivially satisfied), `tests/test_content_e2e.py` (2 Postgres-gated tests: real persistence, edit-creates-new-version-not-new-content).
- **Known, documented limitation (not silently glossed over):** structured brand-voice rules (`forbidden_terms`/`required_keywords`) only activate when the knowledge layer returns them as a dict; real RAG retrieval returns grounded free text, so `ContentAgent.validate_output()` currently falls back to empty rules on real (non-test-mock) knowledge queries. Extracting structured brand-voice profiles from documents is real remaining work, called out explicitly in `test_e2e_scenario.py` and in Remaining Technical Debt below — not something this pass could honestly claim to have solved.
- **Status: FIXED, VERIFIED** (quality engine + brand voice check are unit-tested against real input). Persistence **code-complete, UNVERIFIED at the database level** pending Postgres.

### Finding 6 — Phase 4 GA4/GSC Integrations (was MOCKED, P0 plaintext tokens)
- **Root cause:** `ConnectorToken.access_token`/`refresh_token` were plain `String` columns; `authenticate()` always `INSERT`ed (crashes on re-auth, unique constraint); Celery queue routing didn't match real task names; no idempotency on `NormalizedMetric`; `_trigger_intelligence_layer` was a log line; `ConnectorLog` was never written to.
- **Fix:** New shared `EncryptedString` type (`api/models/types.py`, extracted from the one that already existed unused on `Client`) applied to both token columns — encrypted transparently at the ORM layer. New `BaseConnector._save_token()` upsert helper (get-or-create by `integration_id`) used by both GA4 and GSC connectors' `authenticate()`/`refresh_token()` — the latter now actually persists refreshed tokens instead of discarding them. Fixed Celery `task_routes` to reference real task names (`api.core.tasks.process_report_generation`/`process_content_generation` → `heavy_processing`, `sync_integration_data` → `default`) plus `task_default_queue="default"` as a safety net; added a `celery_beat` service to `docker-compose.yml` to actually drive the schedule. `sync_integration_data` now checks for an existing `NormalizedMetric` by natural key before inserting (updates in place instead of duplicating). Added `reconcile_stale_syncs()` (+ a beat-scheduled task) that closes out `IntegrationSync` rows orphaned "running" by a crashed worker. `_trigger_intelligence_layer` now runs the real `RuleEngine` over provider-mapped metrics (`GA4_FIELD_MAP`/`GSC_FIELD_MAP` translate the generic `value_1..4` columns into named metrics the Rule Engine understands) and writes a real `ConnectorLog` row when a signal fires — the model is no longer dead code. Also fixed real `list_integrations`/`connect_integration`/etc. authorization (see Finding 1/2).
- **Files:** `api/models/types.py` (new), `api/models/client.py`, `api/models/integrations.py`, `api/core/connectors/{base,ga4,gsc}.py`, `api/core/celery_app.py`, `api/core/tasks.py`, `docker-compose.yml`.
- **Tests:** `tests/test_connector_tokens.py` (5 tests: real encrypt/decrypt round-trip + not-plaintext-on-the-wire, upsert-not-duplicate, refresh-token-preserved), `tests/test_celery_wiring.py` (7 tests: routing config actually matches registered task names — a regression guard for the exact bug found — plus aggregation/reconciliation logic).
- **Still MOCKED, unchanged, explicitly not addressed this pass:** the actual OAuth exchange with Google (`authenticate()` still writes literal `"mock_ga4_access_token"` strings) — this needs real Google API credentials and client library integration, out of scope for a takeover-repair pass without those credentials.
- **Status: FIXED (encryption, upsert, queue routing, idempotency, reconciliation, dead-model). VERIFIED via unit tests. OAuth realism: NOT FIXED, correctly still flagged.**

### Addendum (2026-08-16) — Migrations authored and offline-validated

The single largest open item from the repair log below — 21 missing tables, the
`integrations` column drift, and the pgvector extension migration — is now **written**
(5 new migration files: `3f8a1c9d2b47` integrations-fix+membership, `7e2d4f6a8c19`
content domain, `9b5c3e1f7a24` reporting domain, `1d6f8b2a4e93` remaining integrations
domain, `5a3c7e9f1b62` pgvector+document_vectors) and **validated as far as this
environment allows without a live database**: `alembic upgrade head --sql` and
`alembic downgrade head:base --sql` (offline mode - generates real dialect-specific
DDL, executes zero migration-file Python without full import success, but opens no
connection) both succeed end to end against the Postgres dialect, including the exact
`upgrade → downgrade -1 → upgrade` cycle. Also fixed `alembic/env.py`, which
previously always fell back to `alembic.ini`'s static `sqlite:///./test.db` regardless
of the real `DATABASE_URL` - a second, separate way this project could have silently
validated against SQLite instead of Postgres.

This offline validation caught two real, previously-latent bugs in the migrations
authored by the prior agent, now fixed:
1. `c9b6d896812b` (`Initial migration`) referenced `api.models.client.EncryptedString`
   - valid before this repair pass moved that class to `api/models/types.py`, but
   silently broken afterward (ruff's autofix correctly removed the now-locally-unused
   import from `client.py`, not knowing an external migration file depended on it as a
   re-export). Fixed by pointing the migration at the class's real current location.
2. `2c5439b43816` (`Add knowledge models`) contained four `alter_column(...,
   existing_type=sa.NUMERIC(), type_=sa.UUID())` calls - spurious artifacts of
   autogenerating against a stale baseline (`clients.id`/`integrations.id`/
   `integrations.client_id`/`users.id` were already `UUID` from the first migration).
   The **downgrade** direction of these (`UUID → NUMERIC`) is not a valid implicit
   Postgres cast and would have failed outright if ever run for real. Removed as
   genuinely unnecessary in both directions, not just patched.

New regression suite locking this in: `tests/test_migrations.py` (4 tests, run the
above offline validations via subprocess on every `pytest` invocation from now on, no
Postgres required).

**What this does NOT prove**, stated plainly: none of this has executed against an
actual running Postgres server. Offline SQL generation confirms the Python is
syntactically/logically sound and the DDL is dialect-correct - it cannot catch a
constraint violation, a real FK ordering issue only Postgres itself would enforce, or
whether the `vector` extension is actually installed on the target server (confirmed
separately: it is not, on this machine's local Postgres 17). The migrations are
**ready to run** the moment Postgres credentials are available; they have not **run**.

### Finding 7 — Database models & migrations (was BROKEN)
- **Root cause:** `api/models/__init__.py` imported `KnowledgeDocument`/`ContentAsset`, which don't exist — confirmed by direct `ImportError` execution. This alone broke `alembic/env.py` (which already imported the *correct* names) and a live Celery code path.
- **Fix:** Rewrote `api/models/__init__.py` to export every real model class (including the new `ClientMembership`, `ReportComment`, `EncryptedString`/types module) matching what `alembic/env.py` already expected. Fixed the one other reference to the wrong name in `api/core/tasks.py`'s `_ingest_to_knowledge_layer` (was also constructing kwargs that didn't match the real `Document` schema — rewrote to build a real `Document`+`DocumentVersion`+`KnowledgeMetadata`).
- **Files:** `api/models/__init__.py`, `alembic/env.py`, `api/core/tasks.py`.
- **Verification: directly executed — `python -c "import api.models"` and `from api.main import app` both succeed now** (previously both failed).
- **Status: FIXED, VERIFIED (import-level).** **Migration files themselves (19 missing tables, `integrations` column drift, pgvector extension migration) are NOT YET WRITTEN** — this is the one P0 item still fully open, blocked on Postgres credentials (see below). Everything above assumes the eventual migration will match the current, now-correct model definitions.

### Finding 8 — Frontend (was MOCKED, did not build)
- **Root cause:** dead `lucide-react` `Linkedin` import (confirmed build failure); two more version-drift breaks found once the first was fixed (`@clerk/nextjs@7.6.2` no longer exports `SignedIn`/`SignedOut`, and `UserButton` no longer accepts `afterSignOutUrl`); zero API client anywhere; every data page rendered hardcoded arrays; `dashboard/reports`/`dashboard/content` sat outside the `(dashboard)` route group and lost all chrome; `/agents` dead link; hardcoded "Adam B." profile.
- **Fix:** Fixed all three build-breaking API-drift bugs. Built a real typed API client (`src/lib/api.ts`, matches every backend router's actual parameter/body conventions including FastAPI's multi-body-param embedding behavior) bound to Clerk's `getToken()` via `useApiClient()`. Added `@tanstack/react-query` + `sonner` for data fetching/caching and toast feedback. Rewrote every major page (Dashboard, Clients list/detail, Reports, Content, Settings→Integrations, Onboarding) against real endpoints with real loading/error/empty states (`src/components/ui/StateViews.tsx`) — removed every fabricated number (MRR, campaign counts, fake AI activity log, fake "Portfolio Health: 92/100") rather than leaving them in place; where no backend exists yet (Analytics, general Settings, Users), left honest "not built yet" placeholders instead of fabricating data, per the project's own "no false completion" rule. Moved `dashboard/reports`→`(dashboard)/reports` and `dashboard/content`→`(dashboard)/content` (now get sidebar/header like every other page) and updated all nav links. Fixed the `/agents` dead link (removed). Sidebar profile now reads the real signed-in Clerk user. Renamed `middleware.ts`→`proxy.ts` per this Next.js version's (16) renamed convention (functionality unchanged, confirmed by the deprecation warning disappearing from the build). Added a client-picker pattern (`useSelectedClient`, `useSyncExternalStore`-based — not a naive `setState`-in-`useEffect`, which the stricter `react-hooks/set-state-in-effect` lint rule correctly flagged and which was fixed properly rather than suppressed) since reports/content/integrations are all client-scoped but the nav has no per-page client param.
- **Files:** ~20 files across `apps/frontend/src` — see git diff; notably `src/lib/api.ts`, `src/hooks/{useApiClient,useSelectedClient}.ts`, `src/lib/query-provider.tsx`, `src/components/ui/{StateViews,ClientPicker}.tsx` are new.
- **Verification: directly executed.** `npm run build`, `npm run lint`, `npm run typecheck` all pass clean. `npm run dev` was started and loaded in a real browser — **hit a third credential gap: without a real Clerk publishable key, the app hard-crashes before rendering anything (even the public landing page)**, confirmed via console/server logs. Full live click-through verification is blocked on that credential (see below).
- **Status: FIXED (build/lint/typecheck all verified). Live in-browser click-through NOT YET VERIFIED** — blocked on Clerk credentials, not a code issue.

### Finding 9 — Tests & CI (was MOCKED, never run)
- **Root cause:** `.github/workflows/ci.yml`'s pytest step was `echo "Tests placeholder"`; local `.venv` couldn't even run the existing 8 tests (missing `celery`/`redis`/`prometheus_client`/etc., and `pip install -r requirements.txt` failed to build on the installed Python 3.14 from source).
- **Fix:** Installed the missing dependencies as prebuilt wheels (didn't touch `requirements.txt`'s pins, since the Docker image targets Python 3.11 where those exact pins have real wheels — confirmed the local Python 3.14 mismatch was an environment quirk, not a real production bug). Fixed the two test files' missing `UUID` import (a real, if Python-3.14-masked, bug the original audit flagged). Rewrote `ci.yml` end to end: real Postgres 16 + pgvector and Redis service containers (not SQLite), an import-check step, `ruff` lint (scoped to correctness rules — `E`/`F` — with three narrow, justified ignores: `E712` is a false positive against the SQLAlchemy `Column == False` filter idiom, `E402` covers three pre-existing intentional mid-file imports, `E501` is line-length-only), a real `alembic upgrade head → downgrade -1 → upgrade head` verification step, then `pytest tests/ -v` for real. Frontend job now runs lint + typecheck + build (was build-only).
- **Files:** `.github/workflows/ci.yml`, `apps/backend/pyproject.toml` (new, ruff config), `apps/backend/tests/test_{reporting,content}.py` (UUID import fix), plus every new test file listed under Findings 1–6 above (net: 8 → 80 tests, 71 passing + 9 correctly-skipped locally without Postgres).
- **Status: FIXED, VERIFIED locally** (every step of the new CI workflow was run directly in this environment except the Postgres-service-container step, which mirrors the exact local-Postgres migration verification that's still blocked — see below). **NOT YET VERIFIED on actual GitHub Actions infrastructure** (no push was made; this environment has no git remote configured for the repo — see Finding 10).

### Finding 10 — Repository hygiene
- Not addressed this pass: the project root still isn't a git repository, and `apps/frontend`'s nested `.git` is unchanged. This is a repository-structure decision for the user, not something to silently "fix" by running `git init` without being asked.

---

## Still blocked — needs input from you

Two credentials gate the remaining unverified items, discovered and reported in-session:

1. **Local PostgreSQL password.** A real PostgreSQL 17 service is running on this machine, but requires a password this session doesn't have, and lacks the `pgvector` extension (installing it needs admin rights). Blocks: writing/running the 19 missing Alembic migrations, the `integrations` table column-drift fix, the pgvector extension migration, and every Postgres-gated test (`requires_postgres` in `tests/conftest.py` — currently 9 tests skip cleanly rather than being faked against SQLite, per the project's own rule).
2. **Clerk test/dev publishable + secret key pair.** Without one, the frontend cannot render *at all* in a browser (confirmed by actually starting it), so no live click-through, auth-flow, or visual verification could be performed — only static build/lint/typecheck, which all pass.

Redis was self-provisioned this session (installed a portable `redis-windows` build, confirmed `PONG`) and is not blocked.

Everything in this repair log that depends on either credential is marked **"code-complete, UNVERIFIED at the database/browser level"** above, not claimed as done — per the project's own rule that a class existing, or code that hasn't been run, is not proof of a working feature.
