"""Resumo e balanço pelo mês de pagamento: compra no cartão conta no mês em que a fatura vence.

Hoje é 04/11/2026. Cartão A fecha dia 6 e vence dia 12; cartão B fecha dia 29 e vence dia 5.
"""

from datetime import date

import pytest

from financeiro.deps import get_today
from tests.factories import create_card, create_category, create_recurring, create_transaction

TODAY = date(2026, 11, 4)


@pytest.fixture
def november(app):
    app.dependency_overrides[get_today] = lambda: TODAY


@pytest.fixture
def market(client, november):
    return create_category(client)


def card_a(client):
    return create_card(client, name="Cartão A", closing_day=6, due_day=12)


def card_b(client):
    return create_card(client, name="Cartão B", closing_day=29, due_day=5)


def buy(client, category, card, day: str, cents: int):
    return create_transaction(
        client, category["id"], date=day, amount_cents=cents, payment_method="credit_card", card_id=card["id"]
    )


def pay(client, card, invoice_month: str, cents: int):
    payment = {"invoice_month": invoice_month, "paid_on": "2026-11-04", "amount_cents": cents}
    response = client.post(f"/api/cards/{card['id']}/payments", json=payment)
    assert response.status_code == 201, response.text


def summary(client, month: str) -> dict:
    response = client.get("/api/summary/month", params={"month": month})
    assert response.status_code == 200, response.text
    return response.json()


def spending(data: dict) -> tuple[int, int]:
    """(realizado, previsto) das despesas do mês."""
    flows = [data[bucket] for bucket in ("needs", "wants", "savings")]
    return sum(flow["realized_cents"] for flow in flows), sum(flow["pending_cents"] for flow in flows)


@pytest.fixture
def scenario(client, market):
    a, b = card_a(client), card_b(client)
    buy(client, market, a, "2026-10-20", 30_000)  # fatura que vence 12/11: aberta, prevista
    buy(client, market, a, "2026-11-10", 5_000)  # fatura que vence 12/12
    buy(client, market, b, "2026-10-15", 8_000)  # fatura que vence 05/11: paga
    buy(client, market, b, "2026-11-10", 12_000)  # fatura que vence 05/12
    pay(client, b, "2026-10", 8_000)
    create_transaction(client, market["id"], date="2026-11-03", amount_cents=4_000)  # Pix
    create_recurring(
        client,
        market["id"],
        description="Streaming",
        amount_cents=2_000,
        day_of_month=20,
        payment_method="credit_card",
        card_id=b["id"],
        start_month="2026-11",
    )
    return a, b


def test_november_counts_what_is_paid_in_november(client, scenario):
    data = summary(client, "2026-11")
    assert spending(data) == (12_000, 30_000)  # B (paga) + Pix realizados; A aberta, prevista
    assert data["by_category"][0]["total_cents"] == 42_000


def test_purchases_paid_later_go_to_the_later_month(client, scenario):
    a, b = scenario
    november = summary(client, "2026-11")
    assert november["deferred"] == [
        {"card_id": a["id"], "card_name": "Cartão A", "payment_month": "2026-12", "total_cents": 5_000},
        {"card_id": b["id"], "card_name": "Cartão B", "payment_month": "2026-12", "total_cents": 12_000},
    ]
    december = summary(client, "2026-12")
    # dezembro: as compras de novembro (5.000 + 12.000) e a fixa de novembro no cartão B (vence 05/12)
    assert sum(spending(december)) == 19_000


def test_card_recurring_is_listed_by_date_but_counted_in_the_invoice_month(client, scenario):
    november = summary(client, "2026-11")
    assert [(item["description"], item["payment_month"]) for item in november["pending"]] == [
        ("Streaming", "2026-12")
    ]
    assert sum(spending(november)) == 42_000  # a fixa não entra em novembro


def test_partially_paid_invoice_splits_realized_and_pending(client, scenario):
    a, _ = scenario
    client.app.dependency_overrides[get_today] = lambda: date(2026, 11, 8)  # a fatura de A já fechou (06/11)
    pay(client, a, "2026-11", 10_000)
    assert spending(summary(client, "2026-11")) == (22_000, 20_000)


def test_purchase_at_the_end_of_the_month_is_paid_two_months_later(client, market):
    b = card_b(client)
    buy(client, market, b, "2026-11-30", 7_000)
    assert summary(client, "2026-11")["deferred"][0]["payment_month"] == "2027-01"
    assert sum(spending(summary(client, "2026-12"))) == 0
    assert sum(spending(summary(client, "2027-01"))) == 7_000


def test_year_summary_months_add_up_to_the_year(client, scenario):
    response = client.get("/api/summary/year", params={"year": 2026})
    assert response.status_code == 200, response.text
    data = response.json()
    for field in ("needs", "wants", "savings", "income"):
        assert sum(month[field]["total_cents"] for month in data["months"]) == data[field]["total_cents"]
    november = next(month for month in data["months"] if month["month"] == "2026-11")
    assert november["needs"]["total_cents"] == 42_000


def test_without_cards_nothing_changes(client, market):
    create_transaction(client, market["id"], date="2026-11-03", amount_cents=4_000)
    create_transaction(client, market["id"], date="2026-11-20", amount_cents=6_000, payment_method="debit")
    data = summary(client, "2026-11")
    assert spending(data) == (10_000, 0)
    assert data["deferred"] == []


def test_transactions_report_their_payment_month(client, market):
    b = card_b(client)
    buy(client, market, b, "2026-11-10", 1_000)
    create_transaction(client, market["id"], date="2026-11-10", amount_cents=1_000)
    months = {
        item["payment_method"]: item["payment_month"]
        for item in client.get("/api/transactions", params={"month": "2026-11"}).json()
    }
    assert months == {"credit_card": "2026-12", "pix": "2026-11"}
