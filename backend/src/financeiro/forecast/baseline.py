"""Estimativa estatística do total do mês: referência para comparar com o modelo e reserva."""

from datetime import date

from financeiro.domain.months import first_day
from financeiro.forecast.features import HISTORY_MONTHS, days_in, history_months
from financeiro.forecast.history import Expense


def baseline_cents(
    expenses: list[Expense], category_id: int, month: date, today: date, ahead_cents: int
) -> int:
    """Comprometido + média diária do que entra durante o mês × dias que faltam.

    Comprometido: gasto até hoje + o que já se sabe que vem. "O que entra durante o mês" são as
    compras avulsas feitas no próprio mês de pagamento; as de cartão de meses anteriores já estão no
    comprometido e não contam de novo. Sem meses anteriores, projeta o ritmo do mês.
    """
    length = days_in(month)
    day = min(today.day, length)
    cut = date(month.year, month.month, day)
    in_month = [e for e in expenses if e.category_id == category_id and e.month == month]
    spent = sum(e.amount_cents for e in in_month if e.date <= cut)
    recent = history_months(expenses, month)[-HISTORY_MONTHS:]
    if not recent:
        entered = sum(e.amount_cents for e in in_month if _enters(e) and e.date <= cut)
        return spent + ahead_cents + round(entered / day * (length - day))
    variable = sum(
        e.amount_cents for e in expenses if e.category_id == category_id and _enters(e) and e.month in recent
    )
    daily = variable / sum(days_in(m) for m in recent)
    return spent + ahead_cents + round(daily * (length - day))


def _enters(expense: Expense) -> bool:
    """Compra avulsa feita no próprio mês em que é paga (o que a média diária projeta)."""
    return not expense.scheduled and first_day(expense.date) == expense.month
