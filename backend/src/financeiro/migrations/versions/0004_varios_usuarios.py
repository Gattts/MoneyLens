"""vários usuários: cada dado financeiro ganha um dono, e os usuários ganham convite e papel de administrador

Com usuários já cadastrados, todos os dados passam ao de menor id, que vira administrador. Num banco novo (sem
usuário), as categorias, regras e orçamento que as migrações 0001 e 0003 criaram sem dono são apagados: cada usuário
novo recebe o próprio pacote padrão (services/users.py). As tabelas mantêm o RLS da 0002/0003.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-28
"""

import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNED_TABLES = (
    "categories",
    "credit_cards",
    "goals",
    "recurring_rules",
    "transactions",
    "budget_settings",
    "category_rules",
    "invoice_imports",
)
DEFAULTS_WITHOUT_OWNER = ("category_rules", "budget_settings", "categories")
# tabela -> (unicidade antiga, colunas da nova unicidade por usuário)
UNIQUES = {
    "categories": ("uq_categories_name", ["user_id", "name"]),
    "credit_cards": ("uq_credit_cards_name", ["user_id", "name"]),
    "goals": ("uq_goals_name", ["user_id", "name"]),
    "category_rules": ("uq_category_rules_match_type_pattern", ["user_id", "match_type", "pattern"]),
}


def _username_key(name: str) -> str:
    # Cópia de domain/usernames.py no momento desta migração (migrações não importam código do app).
    decomposed = unicodedata.normalize("NFKD", name.strip())
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("username_key", sa.String(length=50), nullable=True))
        batch.add_column(sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("invite_code_hash", sa.String(length=255), nullable=True))
        batch.add_column(sa.Column("invite_expires_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True))
    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
    _assign_owners()
    with op.batch_alter_table("users") as batch:
        batch.alter_column("username_key", existing_type=sa.String(length=50), nullable=False)
        batch.create_unique_constraint(op.f("uq_users_username_key"), ["username_key"])
    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch:
            batch.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
            batch.create_foreign_key(
                op.f(f"fk_{table}_user_id_users"), "users", ["user_id"], ["id"], ondelete="CASCADE"
            )
            if table == "budget_settings":
                batch.create_unique_constraint(op.f("uq_budget_settings_user_id"), ["user_id"])
            else:
                batch.create_index(op.f(f"ix_{table}_user_id"), ["user_id"])
            if table in UNIQUES:
                old, columns = UNIQUES[table]
                batch.drop_constraint(old, type_="unique")
                batch.create_unique_constraint(op.f(f"uq_{table}_{'_'.join(columns)}"), columns)


def _assign_owners() -> None:
    bind = op.get_bind()
    users = bind.execute(sa.text("SELECT id, username FROM users ORDER BY id")).all()
    for user_id, username in users:
        bind.execute(
            sa.text("UPDATE users SET username_key = :key, activated_at = CURRENT_TIMESTAMP WHERE id = :id"),
            {"key": _username_key(username), "id": user_id},
        )
    if not users:
        for table in DEFAULTS_WITHOUT_OWNER:
            op.execute(f"DELETE FROM {table}")  # noqa: S608 - nomes fixos deste arquivo
        return
    owner = users[0][0]
    bind.execute(sa.text("UPDATE users SET is_admin = :yes WHERE id = :id"), {"yes": True, "id": owner})
    for table in OWNED_TABLES:
        bind.execute(sa.text(f"UPDATE {table} SET user_id = :owner"), {"owner": owner})  # noqa: S608


def downgrade() -> None:
    for table in OWNED_TABLES:
        with op.batch_alter_table(table) as batch:
            if table in UNIQUES:
                old, columns = UNIQUES[table]
                batch.drop_constraint(op.f(f"uq_{table}_{'_'.join(columns)}"), type_="unique")
                batch.create_unique_constraint(old, columns[1:])
            if table == "budget_settings":
                batch.drop_constraint(op.f("uq_budget_settings_user_id"), type_="unique")
            else:
                batch.drop_index(op.f(f"ix_{table}_user_id"))
            batch.drop_constraint(op.f(f"fk_{table}_user_id_users"), type_="foreignkey")
            batch.drop_column("user_id")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint(op.f("uq_users_username_key"), type_="unique")
        for column in ("activated_at", "invite_expires_at", "invite_code_hash", "is_admin", "username_key"):
            batch.drop_column(column)
