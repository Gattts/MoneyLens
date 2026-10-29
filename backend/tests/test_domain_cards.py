from datetime import date, timedelta

import pytest

from financeiro.domain.cards import (
    due_date,
    invoice_month_for,
    invoice_period,
    invoice_status,
    open_invoice_start,
    tracked_closed_months,
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


TRACKED = date(2026, 1, 1)


@pytest.mark.parametrize(
    ("today", "total", "paid", "since", "expected"),
    [
        (date(2026, 10, 9), 100, 0, TRACKED, InvoiceStatus.FUTURE),
        (date(2026, 10, 10), 100, 0, TRACKED, InvoiceStatus.OPEN),
        (date(2026, 11, 9), 100, 0, TRACKED, InvoiceStatus.OPEN),
        (date(2026, 11, 10), 100, 0, TRACKED, InvoiceStatus.CLOSED),
        (date(2026, 11, 17), 100, 0, TRACKED, InvoiceStatus.CLOSED),
        (date(2026, 11, 12), 100, 100, TRACKED, InvoiceStatus.PAID),  # paga antes de vencer
        (date(2026, 11, 12), 100, 40, TRACKED, InvoiceStatus.PARTIALLY_PAID),
        (date(2026, 11, 18), 100, 40, TRACKED, InvoiceStatus.PARTIALLY_PAID),
        (date(2026, 11, 18), 100, 0, TRACKED, InvoiceStatus.OVERDUE),
        (date(2026, 11, 18), 0, 0, TRACKED, InvoiceStatus.PAID),  # nada a pagar
        (date(2026, 11, 18), 100, 150, TRACKED, InvoiceStatus.PAID),  # pagou a mais
        (date(2026, 11, 18), 100, 0, date(2026, 11, 18), InvoiceStatus.PAID_BEFORE_TRACKING),
        (date(2026, 11, 18), 100, 0, date(2026, 11, 17), InvoiceStatus.OVERDUE),  # vence no dia do marco
    ],
)
def test_invoice_status_for_november_invoice(today, total, paid, since, expected):
    status = invoice_status(
        date(2026, 11, 1), 10, 17, today, total_cents=total, paid_cents=paid, tracked_since=since
    )
    assert status == expected


def test_open_invoice_start_is_the_last_closing():
    assert open_invoice_start(date(2026, 10, 27), 10) == date(2026, 10, 10)
    assert open_invoice_start(date(2026, 10, 10), 10) == date(2026, 10, 10)
    assert open_invoice_start(date(2026, 10, 9), 10) == date(2026, 9, 10)


def test_tracked_closed_months_start_at_the_first_due_on_or_after_the_mark():
    # Hoje 27/10, fecha 10 e vence 17: já fecharam as faturas de agosto, setembro e outubro.
    assert tracked_closed_months(date(2026, 10, 27), 10, 17, date(2026, 9, 1)) == [
        date(2026, 9, 1),
        date(2026, 10, 1),
    ]
    assert tracked_closed_months(date(2026, 10, 27), 10, 17, date(2026, 10, 17)) == [date(2026, 10, 1)]
    assert tracked_closed_months(date(2026, 10, 27), 10, 17, date(2026, 10, 27)) == []
    # Fecha 28 e vence 5 do mês seguinte: a fatura de outubro vence em 05/11.
    assert tracked_closed_months(date(2026, 11, 1), 28, 5, date(2026, 10, 30)) == [date(2026, 10, 1)]
