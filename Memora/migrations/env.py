import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool
from alembic import context

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import settings
from storage.relational.base import Base
import storage.relational.models

config = context.config

if config.config_file_name is not None:
    # TASK-REL-015: disable_existing_loggers=False is load-bearing. This
    # module is not only run by the alembic CLI: storage.relational.session
    # loads it in-process when init_db() stamps a fresh schema. fileConfig's
    # default (True) disables EVERY logger that already exists and is not
    # named in alembic.ini, silently blinding the host application (and, per
    # PR #107, the test suite) for the rest of the process lifetime.
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata

def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url") or settings.DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)
    if connectable is None:
        url = config.get_main_option("sqlalchemy.url")
        if url and url not in ("sqlite:///./data/memora.db", "sqlite:///"):
            from sqlalchemy import create_engine
            connectable = create_engine(url)
        else:
            from storage.relational.session import engine
            connectable = engine
    
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
