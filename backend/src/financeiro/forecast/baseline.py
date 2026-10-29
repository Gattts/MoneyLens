"""Estimativa estatística do total do mês: referência para comparar com o modelo e reserva."""

from datetime import date

from financeiro.domain.months import first_day
from financeiro.forecast.features import HISTORY_MONTHS, days_in, history_months
from financeiro.forecast.history import Expense


def baseline_cents(
    expenses: list[Expense], category_id: int, month: date, today: date, pending_fixed_cents: int
) -> int:
    """Gasto até hoje + fixas a vir + média diária do variável dos meses anteriores × dias que faltam.

    Sem meses anteriores, projeta o ritmo do mês: gasto até hoje / dias passados × dias do mês.
    """
    length = days_in(month)
    day = min(today.day, length)
    spent = sum(
        e.amount_cents
        for e in expenses
        if e.category_id == category_id and first_day(e.date) == month and e.date.day <= day
    )
    recent = history_months(expenses, month)[-HISTORY_MONTHS:]
    if not recent:
        return round(spent / day * length)
    variable = sum(
        e.amount_cents
        for e in expenses
        if e.category_id == category_id and not e.fixed and first_day(e.date) in recent
    )
    daily = variable / sum(days_in(m) for m in recent)
    return spent + pending_fixed_cents + round(daily * (length - day))
