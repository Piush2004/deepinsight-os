"""
Validates the Alembic migration chain WITHOUT requiring a live database connection,
using `alembic ... --sql` (offline mode) - alembic still fully imports every migration
module and generates real dialect-specific DDL, so this catches real bugs (e.g. a
migration referencing a symbol that no longer exists, or an invalid type cast) even
when no Postgres is reachable. It does NOT prove the DDL executes successfully against
a real server - that's what tests/conftest.py's `requires_postgres`-gated tests are
for, and per project rules we don't pretend this substitutes for that.

This suite is what actually caught two real bugs during the 2026-08-16 migration
authoring pass: c9b6d896812b referencing a symbol (EncryptedString) that had moved
modules, and 2c5439b43816's downgrade attempting an invalid UUID->NUMERIC cast that
would have failed outright against real Postgres.
"""
import subprocess
import sys
import os

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Dialect-only URL for offline SQL generation - alembic never opens a connection in
# --sql mode, this just selects which DDL dialect (Postgres) to render.
DRY_RUN_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/deepinsight_dryrun"


def _run_alembic(*args):
    env = {**os.environ, "DATABASE_URL": DRY_RUN_URL}
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR, env=env, capture_output=True, text=True, timeout=60,
    )
    return result


def test_migration_chain_has_a_single_linear_head():
    result = _run_alembic("heads")
    assert result.returncode == 0, result.stderr
    heads = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(heads) == 1, f"Expected exactly one head (no branches), got: {heads}"


def test_upgrade_head_generates_valid_postgres_ddl_offline():
    result = _run_alembic("upgrade", "head", "--sql")
    assert result.returncode == 0, result.stderr
    assert "CREATE TABLE document_vectors" in result.stdout
    assert "CREATE EXTENSION IF NOT EXISTS vector" in result.stdout
    # Regression guard for the exact bug found in this pass: an invalid cross-type cast.
    assert "NUMERIC" not in result.stdout


def test_downgrade_to_base_generates_valid_postgres_ddl_offline():
    result = _run_alembic("downgrade", "head:base", "--sql")
    assert result.returncode == 0, result.stderr
    assert "DROP TABLE alembic_version" in result.stdout
    assert "NUMERIC" not in result.stdout


def test_upgrade_downgrade_one_upgrade_cycle_offline():
    """Mirrors the exact `upgrade head -> downgrade -1 -> upgrade head` cycle."""
    up = _run_alembic("upgrade", "head", "--sql")
    assert up.returncode == 0, up.stderr

    down_one = _run_alembic("downgrade", "head:1d6f8b2a4e93", "--sql")
    assert down_one.returncode == 0, down_one.stderr

    up_again = _run_alembic("upgrade", "1d6f8b2a4e93:head", "--sql")
    assert up_again.returncode == 0, up_again.stderr
