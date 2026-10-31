"""teto por porcentagem da renda: o teto passa a ser um valor fixo ou uma % da renda prevista do mês

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("spending_limits") as batch:
        batch.add_column(sa.Column("income_percent", sa.Integer(), nullable=True))
        batch.alter_column("amount_cents", existing_type=sa.BigInteger(), nullable=True)
        batch.create_check_constraint(
            op.f("ck_spending_limits_income_percent_range"), "income_percent BETWEEN 1 AND 100"
        )
        batch.create_check_constraint(
            op.f("ck_spending_limits_amount_or_income_percent"),
            "(amount_cents IS NULL) <> (income_percent IS NULL)",
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM spending_limits WHERE amount_cents IS NULL"
    )  # tetos por % não cabem no esquema antigo
    with op.batch_alter_table("spending_limits") as batch:
        batch.drop_constraint(op.f("ck_spending_limits_amount_or_income_percent"), type_="check")
        batch.drop_constraint(op.f("ck_spending_limits_income_percent_range"), type_="check")
        batch.alter_column("amount_cents", existing_type=sa.BigInteger(), nullable=False)
        batch.drop_column("income_percent")
