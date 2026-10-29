"""Medidas que o modelo recebe, iguais no treino e no app.

Cada exemplo é uma fotografia de (categoria, mês, dia d). Os valores em dinheiro são divididos pela escala da
categoria, para o mesmo modelo servir a qualquer nível de gasto.
"""

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from financeiro.domain.months import add_months, first_day
from financeiro.forecast.history import Expense

SNAPSHOT_DAYS = (1, 5, 10, 15, 20, 25)
FEATURE_VERSION = 1  # suba ao mudar as medidas: modelos antigos deixam de ser usados
MIN_SCALE_CENTS = 10_000  # R$ 100
HISTORY_MONTHS = 3  # meses na média
MAX_HISTORY = 6
RECENT_MONTHS = 6  # categoria entra se teve gasto nesse período
SATURDAY = 5  # date.weekday(): sábado e domingo são 5 e 6
WEEKEND_SCALE = 10  # no máximo 10 dias de fim de semana num mês
FEATURE_NAMES = (
    "spent_to_date",
    "fixed_ahead",
    "mean_last_months",
    "last_month",
    "month_fraction",
    "weekends_left",
    "months_of_history",
)


@dataclass(frozen=True)
class Snapshot:
    category_id: int
    month: date
    day: int
    values: tuple[float, ...]
    scale_cents: int
    target_cents: int | None  # total do mês; None no mês atual


def days_in(month: date) -> int:
    return calendar.monthrange(month.year, month.month)[1]


def history_months(expenses: list[Expense], before: date) -> list[date]:
    """Meses anteriores a `before` em que o usuário lançou alguma despesa, em ordem."""
    return sorted({first_day(expense.date) for expense in expenses if first_day(expense.date) < before})


def category_totals(expenses: list[Expense], category_id: int) -> dict[date, int]:
    totals: dict[date, int] = defaultdict(int)
    for expense in expenses:
        if expense.category_id == category_id:
            totals[first_day(expense.date)] += expense.amount_cents
    return totals


def snapshot(
    expenses: list[Expense],
    category_id: int,
    month: date,
    day: int,
    pending_fixed_cents: int | None = None,
) -> Snapshot:
    """Fotografia de um dia. Com `pending_fixed_cents` é o mês atual (sem alvo); sem ele, um mês fechado."""
    current = pending_fixed_cents is not None
    length = days_in(month)
    day = min(day, length)
    in_month = [e for e in expenses if e.category_id == category_id and first_day(e.date) == month]
    spent = sum(e.amount_cents for e in in_month if e.date.day <= day)
    if pending_fixed_cents is None:
        pending_fixed_cents = sum(e.amount_cents for e in in_month if e.fixed and e.date.day > day)
    totals = category_totals(expenses, category_id)
    previous = history_months(expenses, month)
    recent = previous[-HISTORY_MONTHS:]
    mean = sum(totals.get(m, 0) for m in recent) / len(recent) if recent else 0.0
    last = totals.get(add_months(month, -1), 0)
    scale = max(MIN_SCALE_CENTS, round(mean) if mean > 0 else spent)
    weekends = sum(
        1 for d in range(day + 1, length + 1) if date(month.year, month.month, d).weekday() >= SATURDAY
    )
    values = (
        spent / scale,
        pending_fixed_cents / scale,
        mean / scale,
        last / scale,
        day / length,
        weekends / WEEKEND_SCALE,
        min(len(previous), MAX_HISTORY) / MAX_HISTORY,
    )
    target = None if current else totals.get(month, 0)
    return Snapshot(category_id, month, day, values, scale, target)


def training_snapshots(expenses: list[Expense], until_month: date) -> list[Snapshot]:
    """Fotografias com alvo de todos os meses fechados (anteriores a `until_month`)."""
    shots = []
    for month in history_months(expenses, until_month):
        for category_id in _recent_categories(expenses, month, include_month=True):
            for day in SNAPSHOT_DAYS:
                shots.append(snapshot(expenses, category_id, month, day))
    return shots


def categories_to_forecast(expenses: list[Expense], month: date, pending: dict[int, int]) -> list[int]:
    return sorted(set(_recent_categories(expenses, month, include_month=True)) | set(pending))


def _recent_categories(expenses: list[Expense], month: date, *, include_month: bool) -> list[int]:
    start = add_months(month, -RECENT_MONTHS)
    end = add_months(month, 1) if include_month else month
    return sorted({e.category_id for e in expenses if start <= first_day(e.date) < end})
