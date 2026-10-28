import importlib.util
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text

import financeiro
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


def _rules_migration():
    path = Path(financeiro.__file__).parent / "migrations" / "versions" / "0003_leitor_de_faturas.py"
    spec = importlib.util.spec_from_file_location("migration_0003", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_default_rules_are_seeded(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT r.pattern, r.match_type, r.source, c.name FROM category_rules r "
                "JOIN categories c ON c.id = r.category_id"
            )
        ).all()
    default_rules = _rules_migration().DEFAULT_RULES
    assert len(rows) == len(default_rules) > 30
    assert ("UBER", "contains", "default", "Transporte") in rows
    assert ("99FOOD", "contains", "default", "Comida fora") in rows


def test_default_rules_skip_missing_categories(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    config = Config()
    config.set_main_option("script_location", "financeiro:migrations")
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    command.downgrade(config, "0002")
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM categories WHERE name = 'Jogos'"))
    command.upgrade(config, "head")
    with engine.connect() as connection:
        patterns = connection.execute(text("SELECT pattern FROM category_rules")).scalars().all()
    assert "NUUVEM" not in patterns
    assert "UBER" in patterns
