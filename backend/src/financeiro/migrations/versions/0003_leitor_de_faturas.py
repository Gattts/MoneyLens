"""leitor de faturas: regras de categoria, importações, linhas e senha da fatura no cartão

Cria as tabelas do leitor de faturas com a mesma proteção da 0002 no Supabase (RLS sem políticas e sem
acesso pela Data API) e o dicionário inicial de palavras-chave, ligado às categorias padrão que existirem.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("category_rules", "invoice_imports", "invoice_lines")
PUBLIC_API_ROLES = ("anon", "authenticated")

# Palavra-chave (já normalizada: maiúsculas, sem acento) -> categoria padrão. Comparação "contém"; quando duas
# servem, vence a mais longa ("UBER EATS" ganha de "UBER"). Evite palavras curtas que aparecem dentro de outras
# ("MERCADO" pegaria "MERCADOLIVRE", "POSTO" pegaria "IMPOSTO").
DEFAULT_RULES = [
    ("UBER", "Transporte"),
    ("99POP", "Transporte"),
    ("99APP", "Transporte"),
    ("99 TAXI", "Transporte"),
    ("AUTO POSTO", "Transporte"),
    ("IPIRANGA", "Transporte"),
    ("SHELL", "Transporte"),
    ("ESTACIONAMENTO", "Transporte"),
    ("SEM PARAR", "Transporte"),
    ("IFOOD", "Comida fora"),
    ("IFD*", "Comida fora"),
    ("99FOOD", "Comida fora"),
    ("UBER EATS", "Comida fora"),
    ("RAPPI", "Comida fora"),
    ("PIZZ", "Comida fora"),
    ("BURGER", "Comida fora"),
    ("MCDONALDS", "Comida fora"),
    ("RESTAURANTE", "Comida fora"),
    ("LANCHONETE", "Comida fora"),
    ("SUPERMERC", "Mercado"),
    ("MERCADINHO", "Mercado"),
    ("ATACAD", "Mercado"),
    ("ASSAI", "Mercado"),
    ("CARREFOUR", "Mercado"),
    ("HORTIFRUTI", "Mercado"),
    ("PAO DE ACUCAR", "Mercado"),
    ("DROGA", "Farmácia e higiene"),
    ("FARMAC", "Farmácia e higiene"),
    ("PANVEL", "Farmácia e higiene"),
    ("PAGUE MENOS", "Farmácia e higiene"),
    ("SPOTIFY", "Assinaturas"),
    ("NETFLIX", "Assinaturas"),
    ("APPLE.COM", "Assinaturas"),
    ("DISNEY", "Assinaturas"),
    ("GLOBOPLAY", "Assinaturas"),
    ("DEEZER", "Assinaturas"),
    ("YOUTUBE", "Assinaturas"),
    ("PRIME VIDEO", "Assinaturas"),
    ("HBO MAX", "Assinaturas"),
    ("NUUVEM", "Jogos"),
    ("STEAM", "Jogos"),
    ("PLAYSTATION", "Jogos"),
    ("XBOX", "Jogos"),
    ("NINTENDO", "Jogos"),
    ("INGRESSO.COM", "Lazer"),
    ("CINEMA", "Lazer"),
    ("CINEMARK", "Lazer"),
    ("SYMPLA", "Lazer"),
]


def _enum(name: str, *values: str, length: int = 16) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=length)


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("(CURRENT_TIMESTAMP)"),
        nullable=False,
    )


def upgrade() -> None:
    op.add_column(
        "credit_cards", sa.Column("invoice_password_encrypted", sa.String(length=255), nullable=True)
    )
    op.create_table(
        "category_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("pattern", sa.String(length=80), nullable=False),
        sa.Column("match_type", _enum("match_type", "exact", "contains"), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("source", _enum("rule_source", "default", "learned"), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_category_rules_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_category_rules")),
        sa.UniqueConstraint("match_type", "pattern", name=op.f("uq_category_rules_match_type_pattern")),
    )
    op.create_index(op.f("ix_category_rules_category_id"), "category_rules", ["category_id"])
    op.create_table(
        "invoice_imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("bank", sa.String(length=16), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("total_cents", sa.BigInteger(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["credit_cards.id"],
            name=op.f("fk_invoice_imports_card_id_credit_cards"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_imports")),
        sa.UniqueConstraint("card_id", "due_date", name=op.f("uq_invoice_imports_card_id_due_date")),
    )
    op.create_index(op.f("ix_invoice_imports_card_id"), "invoice_imports", ["card_id"])
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=200), nullable=False),
        sa.Column("merchant_key", sa.String(length=200), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("is_credit", sa.Boolean(), nullable=False),
        sa.Column("installment_number", sa.Integer(), nullable=True),
        sa.Column("installment_total", sa.Integer(), nullable=True),
        sa.Column(
            "status", _enum("line_status", "identified", "pending", "imported", "skipped"), nullable=False
        ),
        sa.Column(
            "skip_reason",
            _enum(
                "skip_reason", "payment", "refund", "credit", "duplicate", "existing_installment", length=24
            ),
            nullable=True,
        ),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("rule_id", sa.Integer(), nullable=True),
        sa.Column("transaction_id", sa.Integer(), nullable=True),
        sa.Column("created_installment_group", sa.String(length=32), nullable=True),
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_invoice_lines_amount_positive")),
        sa.CheckConstraint(
            "(status = 'skipped') = (skip_reason IS NOT NULL)",
            name=op.f("ck_invoice_lines_skip_reason_matches_status"),
        ),
        sa.CheckConstraint(
            "status NOT IN ('identified', 'imported') OR category_id IS NOT NULL",
            name=op.f("ck_invoice_lines_category_when_identified"),
        ),
        sa.ForeignKeyConstraint(
            ["import_id"],
            ["invoice_imports.id"],
            name=op.f("fk_invoice_lines_import_id_invoice_imports"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_invoice_lines_category_id_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["rule_id"],
            ["category_rules.id"],
            name=op.f("fk_invoice_lines_rule_id_category_rules"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["transaction_id"],
            ["transactions.id"],
            name=op.f("fk_invoice_lines_transaction_id_transactions"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_invoice_lines")),
        sa.UniqueConstraint("transaction_id", name=op.f("uq_invoice_lines_transaction_id")),
    )
    op.create_index(op.f("ix_invoice_lines_import_id"), "invoice_lines", ["import_id"])
    op.create_index(op.f("ix_invoice_lines_merchant_key"), "invoice_lines", ["merchant_key"])
    op.create_index(op.f("ix_invoice_lines_category_id"), "invoice_lines", ["category_id"])
    _protect_on_supabase()
    _seed_default_rules()


def _protect_on_supabase() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in NEW_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    tables = ", ".join(NEW_TABLES)
    for role in PUBLIC_API_ROLES:
        exists = f"SELECT FROM pg_roles WHERE rolname = '{role}'"  # nosec B608 - constantes deste arquivo
        op.execute(
            f"DO $$ BEGIN IF EXISTS ({exists}) THEN REVOKE ALL ON {tables} FROM {role}; END IF; END $$"
        )


def _seed_default_rules() -> None:
    category_ids = dict(op.get_bind().execute(sa.text("SELECT name, id FROM categories")).all())
    rules = sa.table(
        "category_rules",
        sa.column("pattern", sa.String),
        sa.column("match_type", sa.String),
        sa.column("category_id", sa.Integer),
        sa.column("source", sa.String),
    )
    rows = [
        {"pattern": pattern, "match_type": "contains", "category_id": category_ids[name], "source": "default"}
        for pattern, name in DEFAULT_RULES
        if name in category_ids
    ]
    if rows:
        op.bulk_insert(rules, rows)


def downgrade() -> None:
    op.drop_table("invoice_lines")
    op.drop_table("invoice_imports")
    op.drop_table("category_rules")
    with op.batch_alter_table("credit_cards") as batch:
        batch.drop_column("invoice_password_encrypted")
