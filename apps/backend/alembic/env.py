from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

from api.models.base import Base

target_metadata = Base.metadata

# alembic.ini's sqlalchemy.url is a SQLite fallback for offline tooling only - the
# project's own rule is that SQLite is never a substitute for Postgres validation, so at
# actual migration time we use the real DATABASE_URL the app itself connects with,
# not whatever static value happens to be sitting in the ini file.
import os
_database_url = os.environ.get("DATABASE_URL")
if not _database_url:
    try:
        from api.core.config import settings
        _database_url = settings.DATABASE_URL
    except Exception:
        _database_url = None
if _database_url and not _database_url.startswith("sqlite"):
    config.set_main_option("sqlalchemy.url", _database_url)

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    # See api/database/session.py for why this matters: an unreachable-but-not-refusing
    # Postgres host can otherwise hang `alembic upgrade` indefinitely instead of failing
    # fast with a clear connection error. sqlite3 doesn't accept this kwarg, so it's
    # scoped to Postgres URLs only.
    url = config.get_main_option("sqlalchemy.url", "")
    # See api/database/session.py: 5s, not 10s, because libpq applies this per
    # resolved address (dual-stack "localhost" means ~2x this in the real worst case).
    connect_args = {"connect_timeout": 5} if url.startswith("postgresql") else {}

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
