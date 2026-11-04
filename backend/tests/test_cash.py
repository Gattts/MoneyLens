"""Mês de pagamento: compra no cartão conta no mês em que a fatura vence; o resto, no mês da data."""

from datetime import date

import pytest

from financeiro.domain.cash import CardCycle, due_invoice_month, payment_month, split_paid
from financeiro.domain.enums import Kind, PaymentMethod
from financeiro.models import RecurringRule, Transaction
from tests.factories import create_card, create_category, create_recurring, create_transaction

CARD = PaymentMethod.CREDIT_CARD
EXPENSE = Kind.EXPENSE


@pytest.mark.parametrize(
    ("cycle", "day", "expected"),
    [
        (CardCycle(6, 12), date(2026, 11, 5), date(2026, 11, 1)),  # antes do fechamento: fatura de novembro
        (CardCycle(6, 12), date(2026, 11, 6), date(2026, 12, 1)),  # no dia do fechamento: a seguinte
        (CardCycle(29, 5), date(2026, 11, 28), date(2026, 12, 1)),  # vence no mês seguinte ao fechamento
        (CardCycle(29, 5), date(2026, 11, 30), date(2027, 1, 1)),  # fatura de dezembro, paga em janeiro
        (CardCycle(10, 10), date(2026, 11, 9), date(2026, 12, 1)),  # vence no mesmo dia do fechamento
        (CardCycle(31, 5), date(2026, 2, 27), date(2026, 3, 1)),  # em fevereiro, o dia 31 vira 28
        (CardCycle(31, 5), date(2026, 2, 28), date(2026, 4, 1)),  # e a compra do dia 28 já é do fechamento
        (CardCycle(31, 5), date(2026, 3, 1), date(2026, 4, 1)),
    ],
)
def test_card_purchase_counts_in_the_month_its_invoice_is_due(cycle, day, expected):
    assert payment_month(day, EXPENSE, CARD, cycle) == expected


@pytest.mark.parametrize(
    "method",
    [method for method in PaymentMethod if method is not PaymentMethod.CREDIT_CARD],
)
def test_other_methods_count_in_the_month_of_the_date(method):
    assert payment_month(date(2026, 11, 30), EXPENSE, method, CardCycle(29, 5)) == date(2026, 11, 1)


def test_income_never_changes_month_even_on_the_card():
    assert payment_month(date(2026, 11, 30), Kind.INCOME, CARD, CardCycle(29, 5)) == date(2026, 11, 1)


def test_card_without_cycle_falls_back_to_the_date():
    assert payment_month(date(2026, 11, 30), EXPENSE, CARD, None) == date(2026, 11, 1)


@pytest.mark.parametrize(
    ("month", "cycle", "expected"),
    [
        (date(2026, 11, 1), CardCycle(6, 12), date(2026, 11, 1)),
        (date(2026, 11, 1), CardCycle(29, 5), date(2026, 10, 1)),
        (date(2027, 1, 1), CardCycle(29, 5), date(2026, 12, 1)),
    ],
)
def test_invoice_due_in_a_month(month, cycle, expected):
    assert due_invoice_month(month, cycle) == expected


@pytest.mark.parametrize(
    ("amounts", "paid", "total", "expected"),
    [
        ([100, 200], 300, 300, [(100, 0), (200, 0)]),
        ([100, 200], 0, 300, [(0, 100), (0, 200)]),
        ([100], 500, 100, [(100, 0)]),  # pagou mais que o total: tudo realizado
        ([], 50, 0, []),
        ([100], 0, 0, [(100, 0)]),  # fatura sem total conta como paga
    ],
)
def test_split_paid(amounts, paid, total, expected):
    assert split_paid(amounts, paid, total) == expected


def test_partial_payment_is_proportional_without_losing_cents():
    split = split_paid([101, 202], 150, 303)
    assert [realized + pending for realized, pending in split] == [101, 202]
    assert sum(realized for realized, _ in split) == 150


def test_transaction_and_recurring_rule_know_their_payment_month(client, db):
    card = create_card(client, closing_day=29, due_day=5)
    market = create_category(client)
    on_card = create_transaction(
        client, market["id"], date="2026-10-30", payment_method="credit_card", card_id=card["id"]
    )
    on_pix = create_transaction(client, market["id"], date="2026-10-30")
    rule = create_recurring(client, market["id"], payment_method="credit_card", card_id=card["id"])

    assert db.get(Transaction, on_card["id"]).payment_month == date(2026, 12, 1)
    assert db.get(Transaction, on_pix["id"]).payment_month == date(2026, 10, 1)
    assert db.get(RecurringRule, rule["id"]).payment_month_on(date(2026, 11, 10)) == date(2026, 12, 1)
