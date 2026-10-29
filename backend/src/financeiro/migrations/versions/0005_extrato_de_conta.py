"""extrato de conta: a importação ganha uma origem (fatura ou extrato) e as regras ganham o tipo da categoria

As importações existentes viram faturas de cartão. Um extrato não tem cartão nem vencimento, e sim um período. As
linhas guardam a forma de pagamento (Pix, débito, transferência) e há motivos novos para ficar fora da importação.
Cada regra recebe o tipo da sua categoria, e a mesma palavra pode ter uma regra de despesa e outra de receita. Quem
tem a categoria Investimentos ganha a regra padrão "DINHEIRO GUARDADO". As tabelas mantêm o RLS da 0002/0003.

O downgrade só funciona sem extratos gravados e sem regras repetidas entre tipos.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_SKIP_REASONS = ("payment", "refund", "credit", "duplicate", "existing_installment")
SKIP_REASONS = (
    *OLD_SKIP_REASONS,
    "card_payment",
    "own_transfer",
    "investment",
    "already_imported",
    "ignored",
)
PAYMENT_METHODS = ("pix", "debit", "cash", "bank_slip", "transfer", "credit_card")
SOURCE_CHECK = (
    "(source = 'card_invoice' AND card_id IS NOT NULL AND due_date IS NOT NULL AND period_start IS NULL) "
    "OR (source = 'account_statement' AND card_id IS NULL AND period_start IS NOT NULL AND period_end IS NOT NULL)"
)
STATEMENT_UNIQUE = ["user_id", "bank", "period_start", "period_end"]
OLD_RULE_UNIQUE = ["user_id", "match_type", "pattern"]
RULE_UNIQUE = ["user_id", "kind", "match_type", "pattern"]
SAVED_PATTERN = "DINHEIRO GUARDADO"


def _enum(name: str, *values: str, length: int = 16) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=length)


def _one_of(column: str, values: Sequence[str]) -> str:
    return f"{column} IN ({', '.join(f"'{value}'" for value in values)})"


def _unique_name(table: str, columns: list[str]) -> str:
    return op.f(f"uq_{table}_{'_'.join(columns)}")


def upgrade() -> None:
    with op.batch_alter_table("invoice_imports") as batch:
        source = _enum("import_source", "card_invoice", "account_statement", length=24)
        batch.add_column(sa.Column("source", source, nullable=False, server_default="card_invoice"))
        batch.add_column(sa.Column("period_start", sa.Date(), nullable=True))
        batch.add_column(sa.Column("period_end", sa.Date(), nullable=True))
    with op.batch_alter_table("invoice_imports") as batch:
        # O padrão só servia para as linhas que já existiam; quem grava passa a origem.
        batch.alter_column("source", existing_type=sa.String(length=24), server_default=None)
        batch.alter_column("card_id", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("due_date", existing_type=sa.Date(), nullable=True)
        batch.create_check_constraint(op.f("ck_invoice_imports_source_matches_fields"), SOURCE_CHECK)
        batch.create_unique_constraint(_unique_name("invoice_imports", STATEMENT_UNIQUE), STATEMENT_UNIQUE)
    with op.batch_alter_table("invoice_lines") as batch:
        batch.add_column(
            sa.Column("payment_method", _enum("payment_method", *PAYMENT_METHODS), nullable=True)
        )
        batch.drop_constraint(op.f("ck_invoice_lines_skip_reason"), type_="check")
        batch.create_check_constraint(
            op.f("ck_invoice_lines_skip_reason"), _one_of("skip_reason", SKIP_REASONS)
        )
    with op.batch_alter_table("category_rules") as batch:
        batch.add_column(sa.Column("kind", _enum("kind", "income", "expense"), nullable=True))
    op.execute(
        "UPDATE category_rules SET kind = "
        "(SELECT categories.kind FROM categories WHERE categories.id = category_rules.category_id)"
    )
    with op.batch_alter_table("category_rules") as batch:
        batch.alter_column("kind", existing_type=sa.String(length=16), nullable=False)
        batch.drop_constraint(_unique_name("category_rules", OLD_RULE_UNIQUE), type_="unique")
        batch.create_unique_constraint(_unique_name("category_rules", RULE_UNIQUE), RULE_UNIQUE)
    op.get_bind().execute(
        sa.text(
            "INSERT INTO category_rules (user_id, pattern, match_type, category_id, source, kind) "
            "SELECT c.user_id, CAST(:pattern AS VARCHAR(80)), 'contains', c.id, 'default', 'expense' "
            "FROM categories c "
            "WHERE c.name = 'Investimentos' AND c.kind = 'expense' AND NOT EXISTS ("
            "SELECT 1 FROM category_rules r WHERE r.user_id = c.user_id AND r.kind = 'expense' "
            "AND r.match_type = 'contains' AND r.pattern = CAST(:pattern AS VARCHAR(80)))"
        ),
        {"pattern": SAVED_PATTERN},
    )


def downgrade() -> None:
    with op.batch_alter_table("category_rules") as batch:
        batch.drop_constraint(_unique_name("category_rules", RULE_UNIQUE), type_="unique")
        batch.create_unique_constraint(_unique_name("category_rules", OLD_RULE_UNIQUE), OLD_RULE_UNIQUE)
        batch.drop_column("kind")
    with op.batch_alter_table("invoice_lines") as batch:
        batch.drop_constraint(op.f("ck_invoice_lines_skip_reason"), type_="check")
        batch.create_check_constraint(
            op.f("ck_invoice_lines_skip_reason"), _one_of("skip_reason", OLD_SKIP_REASONS)
        )
        batch.drop_column("payment_method")
    with op.batch_alter_table("invoice_imports") as batch:
        batch.drop_constraint(_unique_name("invoice_imports", STATEMENT_UNIQUE), type_="unique")
        batch.drop_constraint(op.f("ck_invoice_imports_source_matches_fields"), type_="check")
        batch.alter_column("due_date", existing_type=sa.Date(), nullable=False)
        batch.alter_column("card_id", existing_type=sa.Integer(), nullable=False)
        for column in ("period_end", "period_start", "source"):
            batch.drop_column(column)
