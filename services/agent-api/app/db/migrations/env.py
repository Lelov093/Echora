"""Alembic environment configuration for Echora (Windows-compatible).

Reads DATABASE_URL from .env via app.core.config.
Uses sync engine to avoid Windows ProactorEventLoop issues with psycopg async.
"""

import sys
from logging.config import fileConfig

from sqlalchemy import create_engine

from alembic import context

# ── Windows event loop fix ───────────────────────────────────────────
if sys.platform == "win32":
    import asyncio
    import selectors
    try:
        asyncio.set_event_loop_policy(
            asyncio.WindowsSelectorEventLoopPolicy()
        )
    except AttributeError:
        pass  # Python < 3.8

# Load Echora settings (reads .env)
from app.core.config import settings

# Alembic Config object
config = context.config

# Set the database URL from our settings (use sync URL for Alembic)
sync_url = settings.DATABASE_URL.replace("+psycopg", "+psycopg2", 1)
# psycopg 3 supports both sync and async; keep the URL as-is but use create_engine
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Set up logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# For autogenerate: import model MetaData from all application models
from app.db.base import Base
from app.db.models import *  # noqa: F401 F403 — register all models

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
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
    """Run migrations in 'online' mode with sync engine."""
    connectable = create_engine(
        settings.DATABASE_URL,
        echo=settings.APP_ENV == "development",
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
