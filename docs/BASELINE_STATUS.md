# DeepInsight OS — Fresh Baseline Status

**Date:** 2026-08-22
**Purpose:** Phase A of the Infrastructure Closure + Production Verification sprint. Independently re-executed (not assumed) before any code was touched. No application code was modified to produce these results.

## Commands executed

```
cd apps/backend
.venv/Scripts/python.exe -c "import api.models; print('OK')"
.venv/Scripts/python.exe -c "from api.main import app; print('OK', len(app.routes), 'routes')"
.venv/Scripts/python.exe -m pytest tests/ -v
.venv/Scripts/python.exe -m ruff check .

cd apps/frontend
npm run typecheck
npm run lint
npm run build

ollama list
grep OLLAMA_ apps/backend/api/core/config.py
```

## Results

| Check | Result |
|---|---|
| `import api.models` | ✅ OK |
| App boot | ✅ OK, 14 routes registered |
| `pytest tests/ -v` | ✅ **75 passed, 9 skipped, 0 failed** |
| `ruff check .` | ✅ All checks passed |
| Frontend `typecheck` | ✅ 0 errors |
| Frontend `lint` | ✅ 0 errors/warnings |
| Frontend `build` | ✅ succeeds, correct route tree (12 routes) |
| Ollama models present | `qwen2.5:7b-instruct-q4_K_M`, `qwen2.5:3b-instruct`, `nemotron-mini:latest` |
| Configured `OLLAMA_MODEL` default | `"qwen2.5"` — **does not match any pulled tag** (confirmed mismatch persists, see Phase 10 fix in the main sprint report) |

## The 9 skipped tests (unchanged, all Postgres-gated)

```
test_content_e2e.py::test_content_agent_finalize_persists_real_rows
test_content_e2e.py::test_content_agent_edit_creates_new_version_not_new_content
test_e2e_scenario.py::test_full_deepinsight_os_scenario
test_knowledge_e2e.py::test_upload_extracts_chunks_embeds_and_stores_real_rows
test_knowledge_e2e.py::test_duplicate_upload_creates_new_version_not_new_document
test_knowledge_e2e.py::test_retrieval_returns_real_grounded_citation
test_knowledge_e2e.py::test_retrieval_is_tenant_isolated
test_reporting_e2e.py::test_reporting_agent_finalize_persists_real_rows
test_reporting_e2e.py::test_reporting_agent_is_tenant_scoped_on_persist
```

## Differences from the previous report (`docs/LIVE_INFRASTRUCTURE_VERIFICATION.md`, 2026-08-22 earlier same day)

**None.** Exact same pass/skip/fail counts, exact same Ollama model mismatch, exact same clean lint/build state. No drift, no regression, nothing fixed yet (this phase is baseline-only, by design — fixes happen in later phases of this sprint and are reported separately in `docs/INFRASTRUCTURE_CLOSURE_REPORT.md`).

## Environment blockers carried forward (not re-verified in this phase, already established this session)

- Docker daemon unreachable — WSL2 not installed, Windows Home has no Hyper-V fallback, needs admin + reboot to fix.
- Native `postgresql-x64-17` Windows service is running but its password is unknown to this session; `pgvector` extension not installed on it.
- No `.env`/`.env.local` present anywhere (Clerk, encryption key, etc. all unset) — confirmed still true.
