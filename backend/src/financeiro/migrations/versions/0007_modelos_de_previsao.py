"""modelos de previsão: um modelo ONNX por usuário, com versão e métricas

Os modelos são treinados fora do servidor (`financeiro treinar`) e gravados aqui. A tabela recebe a mesma proteção
da 0002/0003/0006 no Supabase (RLS sem políticas e sem acesso das roles da API pública).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PUBLIC_API_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    op.create_table(
        "forecast_models",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "trained_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("trained_until", sa.Date(), nullable=False),
        sa.Column("feature_version", sa.Integer(), nullable=False),
        sa.Column("metrics", sa.Text(), nullable=False),
        sa.Column("onnx", sa.LargeBinary(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_forecast_models_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_forecast_models")),
        sa.UniqueConstraint("user_id", "version", name=op.f("uq_forecast_models_user_id_version")),
    )
    op.create_index(op.f("ix_forecast_models_user_id"), "forecast_models", ["user_id"])
    _protect_on_supabase()


def _protect_on_supabase() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute("ALTER TABLE forecast_models ENABLE ROW LEVEL SECURITY")
    for role in PUBLIC_API_ROLES:
        exists = f"SELECT FROM pg_roles WHERE rolname = '{role}'"  # nosec B608 - constantes deste arquivo
        op.execute(
            f"DO $$ BEGIN IF EXISTS ({exists}) THEN REVOKE ALL ON forecast_models FROM {role}; END IF; END $$"
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_forecast_models_user_id"), table_name="forecast_models")
    op.drop_table("forecast_models")
