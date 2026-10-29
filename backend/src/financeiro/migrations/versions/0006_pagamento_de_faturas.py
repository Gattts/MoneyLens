"""pagamento das faturas: tabela de pagamentos e marco de acompanhamento em cada cartão

Os cartões existentes passam a acompanhar pagamentos a partir da data desta migração; o que venceu antes conta como
pago. A tabela nova recebe a mesma proteção da 0002/0003 no Supabase (RLS sem políticas e sem acesso das roles da
API pública).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLIC_API_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    op.create_table(
        "card_payments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("card_id", sa.Integer(), nullable=False),
        sa.Column("invoice_month", sa.Date(), nullable=False),
        sa.Column("paid_on", sa.Date(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "manual",
                "card_invoice",
                "account_statement",
                name="payment_source",
                native_enum=False,
                create_constraint=True,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column("line_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_card_payments_amount_positive")),
        sa.CheckConstraint(
            "(source = 'manual') = (line_id IS NULL)", name=op.f("ck_card_payments_line_matches_source")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_card_payments_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["card_id"],
            ["credit_cards.id"],
            name=op.f("fk_card_payments_card_id_credit_cards"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["line_id"],
            ["invoice_lines.id"],
            name=op.f("fk_card_payments_line_id_invoice_lines"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_card_payments")),
        sa.UniqueConstraint("line_id", name=op.f("uq_card_payments_line_id")),
    )
    op.create_index(op.f("ix_card_payments_user_id"), "card_payments", ["user_id"])
    op.create_index(op.f("ix_card_payments_card_id"), "card_payments", ["card_id"])
    with op.batch_alter_table("credit_cards") as batch:
        batch.add_column(
            sa.Column("payments_since", sa.Date(), nullable=False, server_default=sa.text("(CURRENT_DATE)"))
        )
    with op.batch_alter_table("credit_cards") as batch:
        # O padrão só servia para os cartões que já existiam; o app grava a data de cada cartão novo.
        batch.alter_column("payments_since", existing_type=sa.Date(), server_default=None)
    _protect_on_supabase()


def _protect_on_supabase() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE card_payments ENABLE ROW LEVEL SECURITY")
    for role in PUBLIC_API_ROLES:
        exists = f"SELECT FROM pg_roles WHERE rolname = '{role}'"  # nosec B608 - constantes deste arquivo
        op.execute(
            f"DO $$ BEGIN IF EXISTS ({exists}) THEN REVOKE ALL ON card_payments FROM {role}; END IF; END $$"
        )


def downgrade() -> None:
    with op.batch_alter_table("credit_cards") as batch:
        batch.drop_column("payments_since")
    op.drop_index(op.f("ix_card_payments_card_id"), table_name="card_payments")
    op.drop_index(op.f("ix_card_payments_user_id"), table_name="card_payments")
    op.drop_table("card_payments")
