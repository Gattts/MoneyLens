"""Ciclo de fatura do cartão de crédito.

A fatura é identificada pelo mês em que fecha. Compras feitas antes do dia de fechamento entram na
fatura daquele mês; a partir do dia de fechamento, entram na seguinte.
"""

from datetime import date

from financeiro.domain.enums import InvoiceStatus
from financeiro.domain.months import add_months, clamp_day, first_day


def closing_date(invoice_month: date, closing_day: int) -> date:
    return clamp_day(invoice_month, closing_day)


def invoice_month_for(purchase: date, closing_day: int) -> date:
    month = first_day(purchase)
    if purchase < closing_date(month, closing_day):
        return month
    return add_months(month, 1)


def invoice_period(invoice_month: date, closing_day: int) -> tuple[date, date]:
    """Compras da fatura: do fechamento anterior (inclusivo) ao fechamento desta (exclusivo)."""
    previous = add_months(invoice_month, -1)
    return closing_date(previous, closing_day), closing_date(invoice_month, closing_day)


def due_date(invoice_month: date, closing_day: int, due_day: int) -> date:
    """Vence no mês do fechamento se o dia de vencimento vem depois dele; senão, no mês seguinte."""
    month = first_day(invoice_month) if due_day > closing_day else add_months(invoice_month, 1)
    return clamp_day(month, due_day)


def invoice_status(
    invoice_month: date,
    closing_day: int,
    due_day: int,
    today: date,
    *,
    total_cents: int,
    paid_cents: int,
    tracked_since: date,
) -> InvoiceStatus:
    """Situação da fatura pelos pagamentos registrados.

    O que venceu antes do marco do cartão (`tracked_since`) conta como pago: o app não registrava pagamentos.
    """
    start, end = invoice_period(invoice_month, closing_day)
    if today < start:
        return InvoiceStatus.FUTURE
    if today < end:
        return InvoiceStatus.OPEN
    due = due_date(invoice_month, closing_day, due_day)
    if due < tracked_since:
        return InvoiceStatus.PAID_BEFORE_TRACKING
    if paid_cents >= total_cents:
        return InvoiceStatus.PAID
    if paid_cents > 0:
        return InvoiceStatus.PARTIALLY_PAID
    return InvoiceStatus.CLOSED if today <= due else InvoiceStatus.OVERDUE


def open_invoice_start(today: date, closing_day: int) -> date:
    """Primeira data de compra da fatura aberta hoje (dali em diante tudo ocupa o limite)."""
    return invoice_period(invoice_month_for(today, closing_day), closing_day)[0]


def tracked_closed_months(today: date, closing_day: int, due_day: int, tracked_since: date) -> list[date]:
    """Faturas já fechadas que vencem a partir do marco: o que falta pagar nelas ocupa o limite."""
    months: list[date] = []
    month = add_months(invoice_month_for(today, closing_day), -1)
    while due_date(month, closing_day, due_day) >= tracked_since:
        months.append(month)
        month = add_months(month, -1)
    return months[::-1]
