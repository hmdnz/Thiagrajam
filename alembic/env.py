# alembic/env.py

from app.database import SQLALCHEMY_DATABASE_URL, Base
import app  # <--- Importing 'app' executes app/__init__.py and registers ALL submodule models


from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

import sys
import os

# Make sure app package can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SQLALCHEMY_DATABASE_URL, Base
from app import models  # noqa: F401


config = context.config

# Use the same database URL as the FastAPI application
config.set_main_option(
    "sqlalchemy.url",
    SQLALCHEMY_DATABASE_URL
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# SQLAlchemy metadata used by Alembic autogenerate
target_metadata = Base.metadata

# List of WIP/unmapped tables to ignore during autogenerate
IGNORED_TABLES = {
    "transactions",
    "payouts",
    "payments",
    "admins",
    "statements",
    "admin_logs",
    "wallets",
    "refunds",
}

def include_object(object, name, type_, reflected, compare_to):
    """Filter out tables from autogenerate checks if they are in IGNORED_TABLES."""
    if type_ == "table" and name in IGNORED_TABLES:
        return False
    return True


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,  # <--- Added here
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in online mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,  # <--- Added here
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()