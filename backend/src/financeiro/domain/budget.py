"""Totais do mês, orçamento 50/30/20 e termômetro financeiro."""

from collections.abc import Iterable
from dataclasses import dataclass, field

from financeiro.domain.enums import Bucket, Kind, Thermometer

FULL_INCOME_PCT = 100


@dataclass(frozen=True)
class Plan:
    needs_pct: int
    wants_pct: int
    savings_pct: int

    def percent(self, bucket: Bucket) -> int:
        return {
            Bucket.NEEDS: self.needs_pct,
            Bucket.WANTS: self.wants_pct,
            Bucket.SAVINGS: self.savings_pct,
        }[bucket]


@dataclass(frozen=True)
class Entry:
    """Um valor do mês: lançamento realizado ou fixa ainda pendente de confirmação."""

    kind: Kind
    bucket: Bucket | None
    amount_cents: int
    pending: bool


@dataclass
class Flow:
    realized: int = 0
    pending: int = 0

    @property
    def total(self) -> int:
        return self.realized + self.pending

    def add(self, amount_cents: int, *, pending: bool) -> None:
        if pending:
            self.pending += amount_cents
        else:
            self.realized += amount_cents


@dataclass
class MonthTotals:
    income: Flow = field(default_factory=Flow)
    expenses: dict[Bucket, Flow] = field(default_factory=lambda: {bucket: Flow() for bucket in Bucket})

    @property
    def spending(self) -> int:
        """Gasto de consumo: necessidades + desejos. Poupança não é gasto."""
        return self.expenses[Bucket.NEEDS].total + self.expenses[Bucket.WANTS].total

    @property
    def balance(self) -> int:
        return self.income.total - sum(flow.total for flow in self.expenses.values())

    @property
    def realized_balance(self) -> int:
        return self.income.realized - sum(flow.realized for flow in self.expenses.values())


@dataclass(frozen=True)
class BudgetLine:
    bucket: Bucket
    percent: int
    planned: int
    used: int

    @property
    def remaining(self) -> int:
        return self.planned - self.used

    @property
    def used_pct(self) -> float | None:
        return None if self.planned == 0 else round(self.used * 100 / self.planned, 1)


def aggregate(entries: Iterable[Entry]) -> MonthTotals:
    totals = MonthTotals()
    for entry in entries:
        if entry.kind is Kind.INCOME:
            totals.income.add(entry.amount_cents, pending=entry.pending)
        elif entry.bucket is not None:
            totals.expenses[entry.bucket].add(entry.amount_cents, pending=entry.pending)
    return totals


def planned_amount(income_cents: int, percent: int) -> int:
    """Percentual da renda em centavos, arredondado para o centavo mais próximo."""
    return (income_cents * percent + 50) // 100


def budget_lines(totals: MonthTotals, plan: Plan) -> list[BudgetLine]:
    return [
        BudgetLine(
            bucket=bucket,
            percent=plan.percent(bucket),
            planned=planned_amount(totals.income.total, plan.percent(bucket)),
            used=totals.expenses[bucket].total,
        )
        for bucket in Bucket
    ]


def thermometer(income_cents: int, spending_cents: int, plan: Plan) -> tuple[Thermometer, float | None]:
    """Compara o gasto de consumo com a renda e com o limite do próprio plano.

    Controlado: gasto dentro de necessidades% + desejos%. Atenção: acima do plano sem passar da
    renda. Negativo: gastou mais do que ganhou.
    """
    if income_cents == 0:
        return (Thermometer.NO_DATA, None) if spending_cents == 0 else (Thermometer.NEGATIVE, None)
    spending_pct = spending_cents * 100 / income_cents
    if spending_pct <= plan.needs_pct + plan.wants_pct:
        status = Thermometer.CONTROLLED
    elif spending_pct <= FULL_INCOME_PCT:
        status = Thermometer.WARNING
    else:
        status = Thermometer.NEGATIVE
    return status, round(spending_pct, 1)
