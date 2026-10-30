"""Tabelas do banco. Valores monetários sempre em centavos (inteiros)."""

import datetime as dt
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    LargeBinary,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from financeiro.domain.enums import (
    Bucket,
    ImportSource,
    Kind,
    LimitAlertKind,
    LineStatus,
    MatchType,
    PaymentMethod,
    PaymentSource,
    RuleSource,
    SkipReason,
)

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


def str_enum(enum_cls: type[StrEnum], name: str, length: int = 16) -> Enum:
    """Enum guardado como texto (o valor, não o nome) com CHECK no banco."""
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        length=length,
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
    # Decide se dois nomes são o mesmo usuário (domain/usernames.py): sem acentos, minúsculas, sem espaços.
    username_key: Mapped[str] = mapped_column(String(50), unique=True)
    is_admin: Mapped[bool] = mapped_column(default=False)
    invite_code_hash: Mapped[str | None] = mapped_column(String(255))
    invite_expires_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    # Nulo enquanto a pessoa não fizer o primeiro acesso.
    activated_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
    password_hash: Mapped[str] = mapped_column(String(255))
    # Incrementado ao trocar a senha: invalida todos os cookies de sessão emitidos antes.
    session_version: Mapped[int] = mapped_column(default=1)


class Category(CreatedAtMixin, Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint(
            "(kind = 'income' AND default_bucket IS NULL) "
            "OR (kind = 'expense' AND default_bucket IS NOT NULL)",
            name="bucket_matches_kind",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    icon: Mapped[str] = mapped_column(String(16), default="")
    description: Mapped[str] = mapped_column(String(300), default="")
    kind: Mapped[Kind] = mapped_column(str_enum(Kind, "kind"))
    default_bucket: Mapped[Bucket | None] = mapped_column(str_enum(Bucket, "default_bucket"))
    archived: Mapped[bool] = mapped_column(default=False)


class CreditCard(CreatedAtMixin, Base):
    __tablename__ = "credit_cards"
    __table_args__ = (
        UniqueConstraint("user_id", "name"),
        CheckConstraint("limit_cents >= 0", name="limit_not_negative"),
        CheckConstraint("closing_day BETWEEN 1 AND 31", name="closing_day_range"),
        CheckConstraint("due_day BETWEEN 1 AND 31", name="due_day_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    limit_cents: Mapped[int] = mapped_column(BigInteger)
    closing_day: Mapped[int]
    due_day: Mapped[int]
    archived: Mapped[bool] = mapped_column(default=False)
    # Faturas que venceram antes desta data contam como pagas: o app ainda não registrava pagamentos.
    payments_since: Mapped[dt.date] = mapped_column(default=dt.date.today)
    # Senha do PDF da fatura, cifrada (services/secret_box.py); nula quando não há senha salva.
    invoice_password_encrypted: Mapped[str | None] = mapped_column(String(255))


class Goal(CreatedAtMixin, Base):
    __tablename__ = "goals"
    __table_args__ = (
        CheckConstraint("target_cents > 0", name="target_positive"),
        UniqueConstraint("user_id", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
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
    """Divisão da renda entre os grupos do orçamento, uma linha por usuário."""

    __tablename__ = "budget_settings"
    __table_args__ = (
        CheckConstraint("needs_pct + wants_pct + savings_pct = 100", name="sum_100"),
        CheckConstraint(
            "needs_pct BETWEEN 0 AND 100 AND wants_pct BETWEEN 0 AND 100 AND savings_pct BETWEEN 0 AND 100",
            name="pct_range",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    needs_pct: Mapped[int] = mapped_column(default=50)
    wants_pct: Mapped[int] = mapped_column(default=30)
    savings_pct: Mapped[int] = mapped_column(default=20)


class CategoryRule(CreatedAtMixin, Base):
    """Reconhece a categoria de uma linha importada pelo nome normalizado do estabelecimento ou da pessoa.

    O tipo é o da categoria: entradas só casam com regras de receita, e saídas com as de despesa.
    """

    __tablename__ = "category_rules"
    __table_args__ = (UniqueConstraint("user_id", "kind", "match_type", "pattern"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pattern: Mapped[str] = mapped_column(String(80))
    match_type: Mapped[MatchType] = mapped_column(str_enum(MatchType, "match_type"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    kind: Mapped[Kind] = mapped_column(str_enum(Kind, "kind"))
    source: Mapped[RuleSource] = mapped_column(str_enum(RuleSource, "rule_source"))


class InvoiceImport(CreatedAtMixin, Base):
    """Uma fatura de cartão ou um extrato de conta lido de um PDF.

    A mesma fatura (cartão + vencimento) e o mesmo extrato (banco + período) não entram duas vezes.
    """

    __tablename__ = "invoice_imports"
    __table_args__ = (
        CheckConstraint(
            "(source = 'card_invoice' AND card_id IS NOT NULL AND due_date IS NOT NULL "
            "AND period_start IS NULL) OR (source = 'account_statement' AND card_id IS NULL "
            "AND period_start IS NOT NULL AND period_end IS NOT NULL)",
            name="source_matches_fields",
        ),
        UniqueConstraint("card_id", "due_date"),
        UniqueConstraint("user_id", "bank", "period_start", "period_end"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    source: Mapped[ImportSource] = mapped_column(
        str_enum(ImportSource, "import_source", length=24), default=ImportSource.CARD_INVOICE
    )
    card_id: Mapped[int | None] = mapped_column(
        ForeignKey("credit_cards.id", ondelete="RESTRICT"), index=True
    )
    bank: Mapped[str] = mapped_column(String(16))
    due_date: Mapped[dt.date | None]
    period_start: Mapped[dt.date | None]
    period_end: Mapped[dt.date | None]
    total_cents: Mapped[int] = mapped_column(BigInteger)
    confirmed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))


class InvoiceLine(Base):
    """Uma linha da fatura: identificada, em standby (pending), importada ou fora da importação."""

    __tablename__ = "invoice_lines"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint(
            "(status = 'skipped') = (skip_reason IS NOT NULL)", name="skip_reason_matches_status"
        ),
        CheckConstraint(
            "status NOT IN ('identified', 'imported') OR category_id IS NOT NULL",
            name="category_when_identified",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("invoice_imports.id", ondelete="CASCADE"), index=True)
    position: Mapped[int]
    date: Mapped[dt.date]
    description: Mapped[str] = mapped_column(String(200))
    merchant_key: Mapped[str] = mapped_column(String(200), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    is_credit: Mapped[bool]
    installment_number: Mapped[int | None]
    installment_total: Mapped[int | None]
    payment_method: Mapped[PaymentMethod | None] = mapped_column(str_enum(PaymentMethod, "payment_method"))
    status: Mapped[LineStatus] = mapped_column(str_enum(LineStatus, "line_status"))
    skip_reason: Mapped[SkipReason | None] = mapped_column(str_enum(SkipReason, "skip_reason", length=24))
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="RESTRICT"), index=True
    )
    rule_id: Mapped[int | None] = mapped_column(ForeignKey("category_rules.id", ondelete="SET NULL"))
    transaction_id: Mapped[int | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="SET NULL"), unique=True
    )
    # Grupo das parcelas futuras que esta linha criou; o "desfazer importação" apaga o grupo inteiro.
    created_installment_group: Mapped[str | None] = mapped_column(String(32))


class CardPayment(CreatedAtMixin, Base):
    """Pagamento (inteiro ou em parte) de uma fatura. Não é lançamento: as compras já são as despesas."""

    __tablename__ = "card_payments"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("(source = 'manual') = (line_id IS NULL)", name="line_matches_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    card_id: Mapped[int] = mapped_column(ForeignKey("credit_cards.id", ondelete="RESTRICT"), index=True)
    invoice_month: Mapped[dt.date]  # mês em que a fatura fecha
    paid_on: Mapped[dt.date]
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    source: Mapped[PaymentSource] = mapped_column(str_enum(PaymentSource, "payment_source", length=24))
    # Linha da importação de onde veio (fatura seguinte ou extrato); desfazer a importação apaga o pagamento.
    line_id: Mapped[int | None] = mapped_column(
        ForeignKey("invoice_lines.id", ondelete="CASCADE"), unique=True
    )


class ForecastModel(Base):
    """Modelo de previsão de um usuário (ONNX), treinado na máquina de quem roda `financeiro treinar`.

    Os pesos são aprendidos com os dados financeiros da pessoa: ficam só no banco, nunca no repositório.
    """

    __tablename__ = "forecast_models"
    __table_args__ = (UniqueConstraint("user_id", "version"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    version: Mapped[int]
    trained_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    trained_until: Mapped[dt.date]  # último mês fechado usado no treino
    feature_version: Mapped[int]
    metrics: Mapped[str] = mapped_column(Text)  # JSON
    onnx: Mapped[bytes] = mapped_column(LargeBinary)


class SpendingLimit(CreatedAtMixin, Base):
    """Teto mensal de gasto de uma categoria de despesa. Vale todo mês até a pessoa mudar o valor."""

    __tablename__ = "spending_limits"
    __table_args__ = (
        UniqueConstraint("user_id", "category_id"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class LimitAlert(CreatedAtMixin, Base):
    """Alerta de um teto num mês. Cada tipo existe uma vez só por teto e mês (não repete)."""

    __tablename__ = "limit_alerts"
    __table_args__ = (UniqueConstraint("limit_id", "month", "kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    limit_id: Mapped[int] = mapped_column(ForeignKey("spending_limits.id", ondelete="CASCADE"), index=True)
    month: Mapped[dt.date]  # primeiro dia do mês
    kind: Mapped[LimitAlertKind] = mapped_column(str_enum(LimitAlertKind, "limit_alert_kind"))
    spent_cents: Mapped[int] = mapped_column(BigInteger)  # no momento do alerta
    limit_cents: Mapped[int] = mapped_column(BigInteger)
    forecast_cents: Mapped[int | None] = mapped_column(BigInteger)  # só no aviso "vai estourar"
    silent: Mapped[bool] = mapped_column(default=False)  # registrado sem avisar (pulo de marcos)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True))
