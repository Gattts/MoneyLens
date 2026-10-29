import importlib.util
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

import financeiro
from financeiro.cli import run_migrations
from financeiro.config import Settings
from financeiro.models import Base


def _settings(tmp_path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path, secret_key="x" * 40)


def _config(settings: Settings) -> Config:
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    config = Config()
    config.set_main_option("script_location", "financeiro:migrations")
    config.set_main_option("sqlalchemy.url", settings.resolved_database_url)
    return config


def test_migrations_create_exactly_the_tables_of_the_models(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.connect() as connection:
        differences = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert differences == []


def test_initial_migration_seeds_default_categories(tmp_path):
    settings = _settings(tmp_path)
    command.upgrade(_config(settings), "0003")
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
    command.upgrade(_config(settings), "0003")
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
    config = _config(settings)
    command.upgrade(config, "0002")
    engine = create_engine(settings.resolved_database_url)
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM categories WHERE name = 'Jogos'"))
    command.upgrade(config, "0003")
    with engine.connect() as connection:
        patterns = connection.execute(text("SELECT pattern FROM category_rules")).scalars().all()
    assert "NUUVEM" not in patterns
    assert "UBER" in patterns


def test_existing_data_goes_to_the_existing_user(tmp_path):
    settings = _settings(tmp_path)
    config = _config(settings)
    command.upgrade(config, "0003")
    engine = create_engine(settings.resolved_database_url)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (username, password_hash, session_version) VALUES ('Joana', 'x', 1)")
        )
        connection.execute(
            text(
                "INSERT INTO credit_cards (name, limit_cents, closing_day, due_day, archived) "
                "VALUES ('Inter', 100, 5, 12, false)"
            )
        )
        # Lançamento apontando para categoria (RESTRICT): recriar a tabela não pode travar nem perder dados.
        connection.execute(
            text(
                "INSERT INTO transactions (description, kind, amount_cents, date, category_id, bucket, "
                "payment_method, notes) SELECT 'Feira', 'expense', 100, '2026-10-01', id, 'needs', 'pix', '' "
                "FROM categories WHERE name = 'Mercado'"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        user = connection.execute(text("SELECT id, username_key, is_admin, activated_at FROM users")).one()
        owners = {
            table: set(connection.execute(text(f"SELECT DISTINCT user_id FROM {table}")).scalars())  # noqa: S608
            for table in ("categories", "category_rules", "credit_cards", "transactions")
        }
    assert user.username_key == "joana"
    assert user.is_admin
    assert user.activated_at is not None
    assert all(found == {user.id} for found in owners.values()), owners


def test_fresh_database_keeps_no_ownerless_rows(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.connect() as connection:
        counts = [
            connection.execute(text(f"SELECT count(*) FROM {table}")).scalar()  # noqa: S608
            for table in ("categories", "category_rules", "budget_settings")
        ]
    assert counts == [0, 0, 0]


def test_checks_survive_the_migration(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (username, username_key, password_hash, session_version, is_admin) "
                "VALUES ('a', 'a', 'x', 1, true)"
            )
        )
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO budget_settings (user_id, needs_pct, wants_pct, savings_pct) "
                "VALUES (1, 90, 30, 20)"
            )
        )


def _insert_rule(connection, user_id: int, pattern: str, category: str) -> None:
    connection.execute(
        text(
            "INSERT INTO category_rules (user_id, pattern, match_type, category_id, source) "
            "SELECT :user, :pattern, 'contains', id, 'learned' FROM categories "
            "WHERE user_id = :user AND name = :name"
        ),
        {"user": user_id, "pattern": pattern, "name": category},
    )


def test_existing_imports_become_card_invoices_and_rules_get_their_kind(tmp_path):
    settings = _settings(tmp_path)
    config = _config(settings)
    command.upgrade(config, "0004")
    engine = create_engine(settings.resolved_database_url)
    with engine.begin() as connection:
        for user_id, name in ((1, "ana"), (2, "bia"), (3, "caio")):
            connection.execute(
                text(
                    "INSERT INTO users (id, username, username_key, password_hash, session_version, "
                    "is_admin) VALUES (:id, :name, :name, 'x', 1, false)"
                ),
                {"id": user_id, "name": name},
            )
        categories = [
            (1, "Investimentos", "expense", "savings"),
            (1, "Salário", "income", None),
            (2, "Investimentos", "expense", "savings"),
            (3, "Mercado", "expense", "needs"),
        ]
        for user_id, name, kind, bucket in categories:
            connection.execute(
                text(
                    "INSERT INTO categories (user_id, name, icon, description, kind, default_bucket, "
                    "archived) VALUES (:user, :name, '', '', :kind, :bucket, false)"
                ),
                {"user": user_id, "name": name, "kind": kind, "bucket": bucket},
            )
        _insert_rule(connection, 1, "UBER", "Investimentos")
        _insert_rule(connection, 1, "EMPRESA", "Salário")
        _insert_rule(connection, 2, "DINHEIRO GUARDADO", "Investimentos")  # já tem: não duplica
        connection.execute(
            text(
                "INSERT INTO credit_cards (user_id, name, limit_cents, closing_day, due_day, archived) "
                "VALUES (1, 'Inter', 100, 5, 12, false)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO invoice_imports (user_id, card_id, bank, due_date, total_cents) "
                "VALUES (1, 1, 'inter', '2026-10-12', 100)"
            )
        )
    command.upgrade(config, "head")
    with engine.connect() as connection:
        source = connection.execute(text("SELECT source FROM invoice_imports")).scalar_one()
        rules = set(
            connection.execute(text("SELECT user_id, pattern, match_type, kind FROM category_rules")).all()
        )
    assert source == "card_invoice"
    assert rules == {
        (1, "UBER", "contains", "expense"),
        (1, "EMPRESA", "contains", "income"),
        (1, "DINHEIRO GUARDADO", "contains", "expense"),
        (2, "DINHEIRO GUARDADO", "contains", "expense"),
    }


def test_new_skip_reasons_and_statement_rows_are_accepted(tmp_path):
    settings = _settings(tmp_path)
    run_migrations(settings)
    engine = create_engine(settings.resolved_database_url)
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users (id, username, username_key, password_hash, session_version, is_admin) "
                "VALUES (1, 'ana', 'ana', 'x', 1, true)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO invoice_imports (id, user_id, source, bank, period_start, period_end, "
                "total_cents) VALUES (1, 1, 'account_statement', 'nubank', '2026-10-01', '2026-10-27', 100)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO invoice_lines (import_id, position, date, description, merchant_key, "
                "amount_cents, is_credit, status, skip_reason, payment_method) VALUES "
                "(1, 1, '2026-10-02', 'LOJA', 'LOJA', 100, false, 'skipped', 'already_imported', 'pix')"
            )
        )
    statement_without_period = (
        "INSERT INTO invoice_imports (user_id, source, bank, total_cents) "
        "VALUES (1, 'account_statement', 'nubank', 1)"
    )
    invoice_without_card = (
        "INSERT INTO invoice_imports (user_id, source, bank, due_date, total_cents) "
        "VALUES (1, 'card_invoice', 'inter', '2026-10-12', 1)"
    )
    for statement in (statement_without_period, invoice_without_card):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement))
