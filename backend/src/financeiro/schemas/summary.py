import datetime as dt

from financeiro.domain.enums import Bucket, Kind, PaymentMethod, Thermometer
from financeiro.schemas.common import Month, OutputModel


class FlowOut(OutputModel):
    realized_cents: int
    pending_cents: int
    total_cents: int


class BudgetLineOut(OutputModel):
    bucket: Bucket
    percent: int
    planned_cents: int
    used_cents: int
    remaining_cents: int
    used_pct: float | None


class ThermometerOut(OutputModel):
    status: Thermometer
    spending_pct: float | None
    limit_pct: int


class CategoryTotalOut(OutputModel):
    category_id: int
    name: str
    icon: str
    total_cents: int


class PendingOut(OutputModel):
    """Ocorrência de uma fixa no mês que ainda não foi confirmada."""

    rule_id: int
    description: str
    kind: Kind
    amount_cents: int
    date: dt.date
    category_id: int
    bucket: Bucket | None
    payment_method: PaymentMethod
    card_id: int | None
    payment_month: Month  # no cartão, o mês em que a fatura vence


class DeferredOut(OutputModel):
    """Compras no cartão feitas no mês que só são pagas num mês seguinte (por cartão e mês de pagamento)."""

    card_id: int
    card_name: str
    payment_month: Month
    total_cents: int


class PeriodTotals(OutputModel):
    income: FlowOut
    needs: FlowOut
    wants: FlowOut
    savings: FlowOut
    balance_cents: int


class MonthSummaryOut(PeriodTotals):
    month: Month
    realized_balance_cents: int
    budget: list[BudgetLineOut]
    thermometer: ThermometerOut
    by_category: list[CategoryTotalOut]
    pending: list[PendingOut]
    deferred: list[DeferredOut]


class YearMonthOut(PeriodTotals):
    month: Month


class YearSummaryOut(PeriodTotals):
    year: int
    months: list[YearMonthOut]
    thermometer: ThermometerOut
