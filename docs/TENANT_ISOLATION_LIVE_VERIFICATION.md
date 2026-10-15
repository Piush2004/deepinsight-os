# Tenant Isolation — Live, Real-HTTP Verification

**Date:** 2026-10-14
**Purpose:** Close the single most-repeated unresolved gap across every prior session's
report in this project: *"the code has never been proven, end-to-end, to actually stop
one real user from reading another real client's real data over HTTP."* This was always
unverifiable before because it required a live Postgres container plus some way to
authenticate as two different real users — both blocked for ~2 months by the Docker
Desktop startup failure root-caused and fixed earlier this session (stale locked Unix
socket files under `%LOCALAPPDATA%`) and by the continued unavailability of real Clerk
credentials.

No application code was changed to produce this result. No test was mocked. No
credentials were invented — real Clerk keys are still unavailable, so this reused the
codebase's own pre-existing, already-built `AUTH_MODE=demo` bypass
(`apps/backend/api/core/security.py`), which:
- is read from `settings.AUTH_MODE`, defaulting to off,
- hard-fails with a `500 Server misconfiguration` if ever combined with
  `ENVIRONMENT=production`,
- replaces only the Clerk JWT *verification* step with trusting an `X-Demo-User`
  header's value as the `sub` claim,
- leaves every line of actual tenant-authorization logic (`ClientMembership`,
  `user_has_client_access`, `assert_client_access`, `require_client_access`) completely
  unchanged — a demo `sub` still has to resolve to a real seeded `User` row and still
  goes through the exact same authorization path a real Clerk user would.

## Method

1. Full Docker stack already live from this session's infrastructure-closure work
   (`deepinsight-postgres`, `deepinsight-redis`, `deepinsight-api`,
   `deepinsight-celery-worker`, `deepinsight-celery-beat`, all healthy).
2. Temporarily added `AUTH_MODE=demo` + `ENVIRONMENT=development` to the `api` and
   `celery_worker` services via the local, gitignored `docker-compose.override.yml`,
   recreated just those two containers (`docker compose up -d --no-deps api
   celery_worker`). Confirmed via `docker exec deepinsight-api printenv`.
3. Ran the project's own existing seed script (`apps/backend/scripts/seed_demo.py`)
   *inside* the live `deepinsight-api` container (so it used the container's real
   `DATABASE_URL`, pointing at the real Postgres container) — not against a local
   SQLite file. This created real rows in the real schema:
   - `demo-admin` — Admin role, membership on all 3 seeded clients.
   - `demo-manager` — Marketing Manager role, membership on **exactly one** client
     (Aurora Wellness Collective), by the script's own design, specifically to make
     this test possible.
   - 3 clients: Aurora Wellness Collective, Northstar Legal Partners, Fernway Outdoor
     Supply.
4. Issued real HTTP requests via `curl` against `http://localhost:8000` (the real
   published container port), authenticating as `demo-manager` via
   `X-Demo-User: demo-manager` (plus a placeholder `Authorization: Bearer` header,
   required only to satisfy FastAPI's `HTTPBearer()` dependency wiring before the demo
   bypass branch is even reached — noted as a minor implementation quirk below, not a
   vulnerability), attempting to read, list, modify, and delete
   **Northstar Legal Partners**, a client `demo-manager` has no membership on.
5. Reverted the override immediately after (`AUTH_MODE`/`ENVIRONMENT` removed), restarted
   `api`/`celery_worker`, and confirmed the real default state returned: `ENVIRONMENT`
   back to `production`, `X-Demo-User` ignored, requests without a real Clerk JWT now
   correctly fail `403 Not authenticated` again.

## Results — real HTTP responses, real Postgres, no mocks

| # | Request (as `demo-manager`, no membership on Northstar) | Expected | Actual |
|---|---|---|---|
| 1 | `GET /api/v1/clients/` | List filtered to own client only | ✅ Returned exactly `["Aurora Wellness Collective"]` |
| 2 | `GET /api/v1/clients/{aurora_id}` (own client) | `200` | ✅ `200` |
| 3 | `GET /api/v1/clients/{northstar_id}` | `404` (not `403` — no existence leak) | ✅ `404 {"detail":"Resource not found"}` |
| 4 | `PUT /api/v1/clients/{northstar_id}` body `{"name":"PWNED"}` | `404`, no mutation | ✅ `404`, confirmed unmodified after |
| 5 | `DELETE /api/v1/clients/{northstar_id}` | blocked | ✅ `403 "Not enough permissions"` — this endpoint is Admin-role-gated ahead of the tenant check; confirmed role-universal (not a tenant-isolation leak) by also attempting `DELETE` on the manager's *own* client (Aurora) and getting the identical `403` |
| 6 | `GET /api/v1/reports?client_id={northstar_id}` | `404` | ✅ `404 {"detail":"Resource not found"}` |
| 7 (control) | `GET /api/v1/clients/{northstar_id}` as `demo-admin` | `200` | ✅ `200`, real row returned — proves the endpoint itself works and isolation isn't just universal breakage |
| 8 (control) | `GET /api/v1/clients/{northstar_id}` as `demo-admin`, post-attack | Unmodified | ✅ Name still `"Northstar Legal Partners"`, not `"PWNED"` |

**Verdict: tenant isolation holds under a real, live, cross-tenant HTTP attack against
real Postgres.** Every attempted read/write/delete across the tenant boundary was
rejected, resource existence was not leaked (404, not 403, for the ownership-gated
paths), and the one 403 observed was confirmed to be a uniform role check rather than a
tenant-specific leak.

## Incidental finding (not a vulnerability, informational)

`FastAPI`'s `HTTPBearer()` security scheme is wired with its default `auto_error=True`,
so it rejects requests lacking *any* `Authorization: Bearer ...` header before
`get_current_user`'s body — and therefore the `AUTH_MODE=demo` branch — ever executes.
In demo mode the token's actual contents are never inspected (only `X-Demo-User` is),
so this just means a caller must send a non-empty placeholder Bearer token alongside
`X-Demo-User` to exercise the bypass. Harmless for the demo path's intended purpose
(local/dev testing without real Clerk keys), but worth knowing if demo mode is ever
scripted again.

## Cleanup performed

- `docker-compose.override.yml` reverted to only its original, still-necessary
  `postgres` port remap (`5433:5432`, for this host's unrelated pre-existing
  `algosherpa-postgres` container conflict) — the temporary `AUTH_MODE`/`ENVIRONMENT`
  block was removed, not left in place.
- `api` and `celery_worker` containers recreated after the revert; confirmed healthy
  and back to `ENVIRONMENT=production` with no demo bypass active.
- Demo seed data (`demo-admin`, `demo-manager`, 3 demo clients, 4 memberships) was left
  in the live `deepinsight` Postgres database — these are inert rows with no PII,
  consistent with the project's existing dev/demo-mode design; delete them manually if a
  clean database is wanted for a subsequent test.

## Net effect on project status

This closes the gap every prior session's report flagged as the single most important
unverified claim in the system. Combined with this session's earlier results (143/143
backend tests passing with zero skips against live Postgres, clean migration
upgrade/downgrade/upgrade cycle, working `pgvector` extension), tenant isolation —
previously "implemented but never proven against real infrastructure" — is now
**verified against a real, live, multi-tenant attack over real HTTP.**

Still unverified / still blocked (unchanged by this work, not to be worked around):
authenticated browser flows via real Clerk (no real Clerk test credentials available),
real Google OAuth for GA4/GSC (intentionally still mocked), live end-to-end Celery task
execution against the real stack, live Knowledge Base document upload via real HTTP.
