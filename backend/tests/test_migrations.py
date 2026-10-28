from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

from financeiro.cli import run_migrations
from financeiro.config import Settings
from financeiro.models import Base


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, secret_key="x" * 40)


def test_migrations_create_exactly_the_tables_of_the_models(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_initial_migration_seeds_default_categories(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.connect() as connection:
        rows = connection.execute(text("SELECT name, kind, default_bucket FROM categories")).all()
    by_name = {name: (kind, bucket) for name, kind, bucket in rows}
    assert by_name["Mercado"] == ("expense", "needs")
    assert by_name["Investimentos"] == ("expense", "savings")
    assert by_name["Salário"] == ("income", None)
    assert "Necessidades" not in by_name  # o nome colidia com o grupo do orçamento na planilha


def test_migrations_are_idempotent(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    assert "transactions" in inspect(engine).get_table_names()
