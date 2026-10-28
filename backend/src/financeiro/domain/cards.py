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


def invoice_status(invoice_month: date, closing_day: int, due_day: int, today: date) -> InvoiceStatus:
    start, end = invoice_period(invoice_month, closing_day)
    if today < start:
        return InvoiceStatus.FUTURE
    if today < end:
        return InvoiceStatus.OPEN
    if today <= due_date(invoice_month, closing_day, due_day):
        return InvoiceStatus.CLOSED
    return InvoiceStatus.PAST


def limit_usage_start(today: date, closing_day: int, due_day: int) -> date:
    """Primeira data de compra que ainda ocupa o limite do cartão.

    Ocupam o limite a fatura aberta, a fatura fechada que ainda não venceu e as parcelas futuras.
    A ferramenta não registra o pagamento da fatura, então considera paga a fatura já vencida.
    """
    current = invoice_month_for(today, closing_day)
    previous = add_months(current, -1)
    oldest_unpaid = previous if due_date(previous, closing_day, due_day) >= today else current
    return invoice_period(oldest_unpaid, closing_day)[0]
