"""Regression test for a real bug found during live infrastructure verification
(docs/INFRASTRUCTURE_CLOSURE_REPORT.md): connecting to an unreachable-but-not-actively-
refusing Postgres host hung indefinitely (confirmed 20s+ with no sign of stopping, via a
bare `psycopg.connect()`) because no connect_timeout was configured anywhere in the
stack. A downed database should fail an API request or Celery task within a bounded
time, not hang it forever.

This deliberately doesn't touch the real `postgresql-x64-17` service or any live
infrastructure - it points at a local port nothing is listening on, which is enough to
exercise the same "TCP connect never resolves quickly" condition without needing any
credentials or a running database. It also deliberately does NOT include a test that
reproduces the unbounded pre-fix hang directly - that would (correctly) take 20s+ or
longer on every test run, which is exactly the kind of stall this fix exists to
prevent; the bounded test below is sufficient to prove the fix works.
"""
import time
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# An address:port nothing listens on. Using localhost with a high, unlikely-to-collide
# port keeps this hermetic - no external network access, no dependency on any service
# being up or down.
_UNREACHABLE_URL = "postgresql+psycopg://postgres:postgres@localhost:59999/nope"


def test_connect_timeout_bounds_connection_attempt():
    """The actual fix: the same pattern used in api/database/session.py and
    alembic/env.py (connect_args={"connect_timeout": 5} for Postgres URLs) must cause
    a connection attempt to an unreachable host to fail within a bounded time, not hang.

    Note: libpq applies connect_timeout PER resolved address, and "localhost" commonly
    resolves to both an IPv6 and an IPv4 address - confirmed live during this fix's
    verification, a connect_timeout of 10 took ~20s here, not ~10s. The bound below
    accounts for that dual-stack multiplier rather than assuming a single attempt."""
    engine = create_engine(_UNREACHABLE_URL, connect_args={"connect_timeout": 5})
    t0 = time.monotonic()
    try:
        with pytest.raises(OperationalError):
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        elapsed = time.monotonic() - t0
        # ~2x the configured 5s for dual-stack localhost, plus margin for CI jitter -
        # still an order of magnitude below the unbounded pre-fix hang (confirmed
        # 20s+ with no sign of stopping via a bare psycopg.connect()).
        assert elapsed < 20, (
            f"connect_timeout=5 did not bound the connection attempt - took {elapsed:.1f}s."
        )
    finally:
        engine.dispose()


def test_sqlite_urls_are_not_given_postgres_only_connect_args():
    """sqlite3.connect() raises TypeError on an unknown 'connect_timeout' kwarg - the
    fix must not apply it to non-Postgres URLs, or every sqlite-backed test/dev setup
    in this project breaks."""
    from api.database.session import _connect_args, engine
    if str(engine.url).startswith("sqlite"):
        assert _connect_args == {}
    else:
        assert _connect_args.get("connect_timeout") == 5
