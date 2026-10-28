"""protege as tabelas no Supabase: RLS ligado e sem acesso pela Data API

No Supabase, tudo no schema public fica exposto pela Data API (PostgREST) aos papéis `anon` e
`authenticated`, e a chave `anon` é pública. A aplicação não usa essa API: o backend conecta como
dono das tabelas, que não é afetado pelo RLS. Ligar o RLS sem políticas e revogar os privilégios
desses papéis fecha a porta. Em SQLite esta migração não faz nada.

Toda migração que criar uma tabela nova precisa repetir isto para ela; tests/test_postgres.py
confere todas as tabelas dos modelos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-27
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = (
    "users",
    "categories",
    "credit_cards",
    "goals",
    "recurring_rules",
    "transactions",
    "budget_settings",
    "alembic_version",
)
PUBLIC_API_ROLES = ("anon", "authenticated")


def upgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    tables = ", ".join(TABLES)
    for role in PUBLIC_API_ROLES:
        # Os papéis só existem no Supabase; num Postgres comum, nada a revogar.
        exists = f"SELECT FROM pg_roles WHERE rolname = '{role}'"  # nosec B608 - constantes deste arquivo
        op.execute(
            f"DO $$ BEGIN IF EXISTS ({exists}) THEN REVOKE ALL ON {tables} FROM {role}; END IF; END $$"
        )


def downgrade() -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
