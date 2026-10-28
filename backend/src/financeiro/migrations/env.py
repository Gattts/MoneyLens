from logging.config import fileConfig
from typing import Any

from alembic import context
from sqlalchemy.engine import Connection

from financeiro.config import get_settings
from financeiro.db import create_db_engine
from financeiro.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().resolved_database_url


def _configure(**options: Any) -> None:
    # render_as_batch: o SQLite não altera colunas/restrições no lugar; o Alembic recria a tabela.
    context.configure(target_metadata=target_metadata, render_as_batch=True, compare_type=True, **options)


def run_migrations_offline() -> None:
    _configure(url=_database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def _run_with(connection: Connection) -> None:
    _configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_db_engine(_database_url())
    with engine.connect() as connection:
        _run_with(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
