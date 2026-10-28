"""Tabelas do banco. Valores monetários sempre em centavos (inteiros)."""

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    MetaData,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from financeiro.domain.enums import Bucket, Kind, PaymentMethod

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

BUCKET_MATCHES_KIND = "(kind = 'income' AND bucket IS NULL) OR (kind = 'expense' AND bucket IS NOT NULL)"
CARD_MATCHES_PAYMENT = (
    "(payment_method = 'credit_card' AND card_id IS NOT NULL) "
    "OR (payment_method != 'credit_card' AND card_id IS NULL)"
)


def str_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    """Enum guardado como texto (o valor, não o nome) com CHECK no banco."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=16,
        values_callable=lambda members: [member.value for member in members],
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class CreatedAtMixin:
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    # Incrementado ao trocar a senha: invalida todos os cookies de sessão emitidos antes.
    session_version: Mapped[int] = mapped_column(default=1)


class Category(CreatedAtMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint(
            "(kind = 'income' AND default_bucket IS NULL) "
            "OR (kind = 'expense' AND default_bucket IS NOT NULL)",
            name="bucket_matches_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    icon: Mapped[str] = mapped_column(String(16), default="")
    description: Mapped[str] = mapped_column(String(300), default="")
    kind: Mapped[Kind] = mapped_column(str_enum(Kind, "kind"))
    default_bucket: Mapped[Bucket | None] = mapped_column(str_enum(Bucket, "default_bucket"))
    archived: Mapped[bool] = mapped_column(default=False)


class CreditCard(CreatedAtMixin, Base):
    __tablename__ = "credit_cards"
    __table_args__ = (
        CheckConstraint("limit_cents >= 0", name="limit_not_negative"),
        CheckConstraint("closing_day BETWEEN 1 AND 31", name="closing_day_range"),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="due_day_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    limit_cents: Mapped[int] = mapped_column(BigInteger)
    closing_day: Mapped[int]
    due_day: Mapped[int]
    archived: Mapped[bool] = mapped_column(default=False)


class Goal(CreatedAtMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (CheckConstraint("target_cents > 0", name="target_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True)
    icon: Mapped[str] = mapped_column(String(16), default="")
    target_cents: Mapped[int] = mapped_column(BigInteger)
    target_date: Mapped[dt.date | None]
    archived: Mapped[bool] = mapped_column(default=False)


class RecurringRule(CreatedAtMixin, Base):
    __tablename__ = "recurring_rules"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("day_of_month BETWEEN 1 AND 31", name="day_range"),
        CheckConstraint("end_month IS NULL OR end_month >= start_month", name="end_after_start"),
        CheckConstraint(BUCKET_MATCHES_KIND, name="bucket_matches_kind"),
        CheckConstraint(CARD_MATCHES_PAYMENT, name="card_matches_payment"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(120))
    kind: Mapped[Kind] = mapped_column(str_enum(Kind, "kind"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"))
    bucket: Mapped[Bucket | None] = mapped_column(str_enum(Bucket, "bucket"))
    day_of_month: Mapped[int]
    payment_method: Mapped[PaymentMethod] = mapped_column(str_enum(PaymentMethod, "payment_method"))
    card_id: Mapped[int | None] = mapped_column(ForeignKey("credit_cards.id", ondelete="RESTRICT"))
    start_month: Mapped[dt.date]
    end_month: Mapped[dt.date | None]
    notes: Mapped[str] = mapped_column(String(500), default="")


class Transaction(CreatedAtMixin, Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(BUCKET_MATCHES_KIND, name="bucket_matches_kind"),
        CheckConstraint(CARD_MATCHES_PAYMENT, name="card_matches_payment"),
        CheckConstraint("goal_id IS NULL OR bucket = 'savings'", name="goal_only_on_savings"),
        CheckConstraint(
            "(installment_group IS NULL AND installment_number IS NULL AND installment_total IS NULL) "
            "OR (installment_group IS NOT NULL AND installment_number BETWEEN 1 AND installment_total)",
            name="installment_consistency",
        ),
        CheckConstraint("recurring_rule_id IS NULL OR recurrence_month IS NOT NULL", name="recurrence_month"),
        # Confirmar a mesma fixa duas vezes no mesmo mês (ex.: clique duplo) é barrado pelo banco.
        UniqueConstraint("recurring_rule_id", "recurrence_month"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    description: Mapped[str] = mapped_column(String(120))
    kind: Mapped[Kind] = mapped_column(str_enum(Kind, "kind"))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    date: Mapped[dt.date] = mapped_column(index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="RESTRICT"), index=True)
    bucket: Mapped[Bucket | None] = mapped_column(str_enum(Bucket, "bucket"))
    payment_method: Mapped[PaymentMethod] = mapped_column(str_enum(PaymentMethod, "payment_method"))
    card_id: Mapped[int | None] = mapped_column(
        ForeignKey("credit_cards.id", ondelete="RESTRICT"), index=True
    )
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("goals.id", ondelete="SET NULL"), index=True)
    notes: Mapped[str] = mapped_column(String(500), default="")
    installment_group: Mapped[str | None] = mapped_column(String(32), index=True)
    installment_number: Mapped[int | None]
    installment_total: Mapped[int | None]
    recurring_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_rules.id", ondelete="SET NULL")
    )
    recurrence_month: Mapped[dt.date | None]


class BudgetSettings(Base):
    """Linha única (id = 1) com a divisão da renda entre os grupos do orçamento."""

    __tablename__ = "budget_settings"
    __table_args__ = (
        CheckConstraint("needs_pct + wants_pct + savings_pct = 100", name="sum_100"),
        CheckConstraint(
            "needs_pct BETWEEN 0 AND 100 AND wants_pct BETWEEN 0 AND 100 AND savings_pct BETWEEN 0 AND 100",
            name="pct_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    needs_pct: Mapped[int] = mapped_column(default=50)
    wants_pct: Mapped[int] = mapped_column(default=30)
    savings_pct: Mapped[int] = mapped_column(default=20)
