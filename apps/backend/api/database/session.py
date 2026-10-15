from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from api.core.config import settings

# A Postgres host that's down/unreachable at the network level (not just rejecting
# credentials) can otherwise hang a request or Celery task indefinitely - a TCP SYN to
# a closed/filtered port doesn't always fail fast on every OS/network stack (confirmed
# directly during infra-closure verification: a bare psycopg.connect() to an
# unreachable port hung 20s+ with no sign of stopping). sqlite3's connect() doesn't
# accept this kwarg, so it's scoped to Postgres URLs only - the sqlite fallback used by
# many unit tests must stay unaffected.
#
# Note: libpq applies connect_timeout PER resolved address, not per connection attempt
# overall - "localhost" commonly resolves to both an IPv6 and an IPv4 address, so the
# real worst case observed here is roughly 2x this value, not exactly this value. Kept
# at 5s (not 10s) specifically so that worst case stays well under production request
# timeouts even with dual-stack resolution.
_connect_args = {"connect_timeout": 5} if settings.DATABASE_URL.startswith("postgresql") else {}

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
