from datetime import date, timedelta

import pytest

from financeiro.domain.cards import (
    due_date,
    invoice_month_for,
    invoice_period,
    invoice_status,
    limit_usage_start,
)
from financeiro.domain.enums import InvoiceStatus


@pytest.mark.parametrize(
    ("purchase", "closing_day", "expected"),
    [
        (date(2026, 10, 9), 10, date(2026, 10, 1)),  # véspera do fechamento: fatura de outubro
        (date(2026, 10, 10), 10, date(2026, 11, 1)),  # no dia do fechamento: já é a próxima
        (date(2026, 10, 25), 10, date(2026, 11, 1)),
        (date(2026, 12, 20), 5, date(2027, 1, 1)),  # vira o ano
        (date(2026, 2, 27), 31, date(2026, 2, 1)),
        (date(2026, 2, 28), 31, date(2026, 3, 1)),  # fechamento 31 vira 28 em fevereiro
        (date(2026, 4, 30), 31, date(2026, 5, 1)),
    ],
)
def test_invoice_month_for_uses_closing_day(purchase, closing_day, expected):
    assert invoice_month_for(purchase, closing_day) == expected


@pytest.mark.parametrize(
    ("invoice_month", "closing_day", "expected"),
    [
        (date(2026, 11, 1), 10, (date(2026, 10, 10), date(2026, 11, 10))),
        (date(2026, 3, 1), 31, (date(2026, 2, 28), date(2026, 3, 31))),
        (date(2027, 1, 1), 5, (date(2026, 12, 5), date(2027, 1, 5))),
    ],
)
def test_invoice_period_goes_from_previous_closing_to_this_closing(invoice_month, closing_day, expected):
    assert invoice_period(invoice_month, closing_day) == expected


def test_every_purchase_falls_inside_the_period_of_its_invoice():
    day = date(2024, 1, 1)
    while day <= date(2025, 12, 31):
        for closing_day in range(1, 32):
            start, end = invoice_period(invoice_month_for(day, closing_day), closing_day)
            assert start <= day < end, (day, closing_day)
        day += timedelta(days=1)


@pytest.mark.parametrize(
    ("invoice_month", "closing_day", "due_day", "expected"),
    [
        (date(2026, 11, 1), 10, 17, date(2026, 11, 17)),  # vence no mesmo mês do fechamento
        (date(2026, 11, 1), 28, 5, date(2026, 12, 5)),  # vence no mês seguinte
        (date(2026, 11, 1), 25, 25, date(2026, 12, 25)),
        (date(2026, 2, 1), 1, 31, date(2026, 2, 28)),
    ],
)
def test_due_date(invoice_month, closing_day, due_day, expected):
    assert due_date(invoice_month, closing_day, due_day) == expected


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (date(2026, 10, 9), InvoiceStatus.FUTURE),
        (date(2026, 10, 10), InvoiceStatus.OPEN),
        (date(2026, 11, 9), InvoiceStatus.OPEN),
        (date(2026, 11, 10), InvoiceStatus.CLOSED),
        (date(2026, 11, 17), InvoiceStatus.CLOSED),
        (date(2026, 11, 18), InvoiceStatus.PAST),
    ],
)
def test_invoice_status_for_november_invoice(today, expected):
    assert invoice_status(date(2026, 11, 1), 10, 17, today) == expected


@pytest.mark.parametrize(
    ("today", "closing_day", "due_day", "expected"),
    [
        # Fatura de novembro fechou dia 10 e vence dia 17: ainda ocupa o limite.
        (date(2026, 11, 12), 10, 17, date(2026, 10, 10)),
        # Depois do vencimento, só a fatura aberta (dezembro) em diante ocupa o limite.
        (date(2026, 11, 20), 10, 17, date(2026, 11, 10)),
        # Fechamento 28 e vencimento 5 do mês seguinte.
        (date(2026, 12, 3), 28, 5, date(2026, 10, 28)),
    ],
)
def test_limit_usage_start_includes_closed_invoice_until_due_date(today, closing_day, due_day, expected):
    assert limit_usage_start(today, closing_day, due_day) == expected
