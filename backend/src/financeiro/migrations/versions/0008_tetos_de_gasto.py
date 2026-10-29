"""tetos de gasto: um teto mensal por categoria de despesa e os alertas de cada teto por mês

As tabelas recebem a mesma proteção da 0002/0003/0006/0007 no Supabase (RLS sem políticas e sem acesso das roles
da API pública).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLIC_API_ROLES = ("anon", "authenticated")
TABLES = ("spending_limits", "limit_alerts")
ALERT_KINDS = ("reached_50", "reached_90", "reached_100", "forecast")


def upgrade() -> None:
    op.create_table(
        "spending_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("amount_cents", sa.BigInteger(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint("amount_cents > 0", name=op.f("ck_spending_limits_amount_positive")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_spending_limits_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            name=op.f("fk_spending_limits_category_id_categories"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_spending_limits")),
        sa.UniqueConstraint("user_id", "category_id", name=op.f("uq_spending_limits_user_id_category_id")),
    )
    op.create_index(op.f("ix_spending_limits_user_id"), "spending_limits", ["user_id"])
    op.create_index(op.f("ix_spending_limits_category_id"), "spending_limits", ["category_id"])
    kinds = ", ".join(f"'{kind}'" for kind in ALERT_KINDS)
    op.create_table(
        "limit_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("limit_id", sa.Integer(), nullable=False),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("spent_cents", sa.BigInteger(), nullable=False),
        sa.Column("limit_cents", sa.BigInteger(), nullable=False),
        sa.Column("forecast_cents", sa.BigInteger(), nullable=True),
        sa.Column("silent", sa.Boolean(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(f"kind IN ({kinds})", name=op.f("ck_limit_alerts_limit_alert_kind")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_limit_alerts_user_id_users"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["limit_id"],
            ["spending_limits.id"],
            name=op.f("fk_limit_alerts_limit_id_spending_limits"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_limit_alerts")),
        sa.UniqueConstraint("limit_id", "month", "kind", name=op.f("uq_limit_alerts_limit_id_month_kind")),
    )
    op.create_index(op.f("ix_limit_alerts_user_id"), "limit_alerts", ["user_id"])
    op.create_index(op.f("ix_limit_alerts_limit_id"), "limit_alerts", ["limit_id"])
    _protect_on_supabase()


def _protect_on_supabase() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        for role in PUBLIC_API_ROLES:
            exists = f"SELECT FROM pg_roles WHERE rolname = '{role}'"  # nosec B608 - constantes deste arquivo
            op.execute(
                f"DO $$ BEGIN IF EXISTS ({exists}) THEN REVOKE ALL ON {table} FROM {role}; END IF; END $$"
            )


def downgrade() -> None:
    op.drop_index(op.f("ix_limit_alerts_limit_id"), table_name="limit_alerts")
    op.drop_index(op.f("ix_limit_alerts_user_id"), table_name="limit_alerts")
    op.drop_table("limit_alerts")
    op.drop_index(op.f("ix_spending_limits_category_id"), table_name="spending_limits")
    op.drop_index(op.f("ix_spending_limits_user_id"), table_name="spending_limits")
    op.drop_table("spending_limits")
