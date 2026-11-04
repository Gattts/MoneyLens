"""Tetos pelo mês de pagamento: uma compra no cartão conta no teto do mês em que a fatura vence.

Hoje (testes) é 27/10/2026. O cartão fecha dia 20 e vence dia 28: a compra de hoje cai na fatura que
vence em 28/11.
"""

from datetime import date

import pytest
from sqlalchemy import select

from financeiro.deps import get_today
from financeiro.models import LimitAlert
from financeiro.services import limits
from tests.factories import (
    create_card,
    create_category,
    create_income_category,
    create_limit,
    create_transaction,
)


@pytest.fixture
def food(client):
    return create_category(client, name="Comida fora", default_bucket="wants")


@pytest.fixture
def card(client):
    return create_card(client, closing_day=20, due_day=28)


def buy(client, category, card, cents: int, day: str = "2026-10-27"):
    return create_transaction(
        client, category["id"], amount_cents=cents, date=day, payment_method="credit_card", card_id=card["id"]
    )


def limit_in(client, month: str | None = None) -> dict:
    params = {"month": month} if month else {}
    response = client.get("/api/limits", params=params)
    assert response.status_code == 200, response.text
    [item] = response.json()
    return item


def alerts(client) -> list[dict]:
    response = client.get("/api/alerts")
    assert response.status_code == 200, response.text
    return response.json()["items"]


def test_card_purchase_counts_in_the_limit_of_the_month_it_is_paid(client, food, card):
    create_limit(client, food["id"], amount_cents=10_000)
    buy(client, food, card, 9_500)
    assert limit_in(client)["spent_cents"] == 0
    november = limit_in(client, "2026-11")
    assert (november["spent_cents"], november["percent"]) == (9_500, 95)


def test_alert_is_recorded_for_the_month_it_is_paid(client, food, card):
    create_limit(client, food["id"], amount_cents=10_000)
    buy(client, food, card, 9_500)
    assert [(item["kind"], item["month"]) for item in alerts(client)] == [("reached_90", "2026-11")]


def test_end_of_month_purchase_alerts_two_months_ahead(app, client, food):
    app.dependency_overrides[get_today] = lambda: date(2026, 11, 30)
    late_card = create_card(client, name="Fecha 29", closing_day=29, due_day=5)
    create_limit(client, food["id"], amount_cents=10_000)
    buy(client, food, late_card, 10_000, day="2026-11-30")
    assert [(item["kind"], item["month"]) for item in alerts(client)] == [("reached_100", "2027-01")]


def test_will_exceed_only_in_the_current_month(client, food, card, monkeypatch):
    monkeypatch.setattr(limits, "forecast_p50", lambda *_args: {food["id"]: 1_000_000})
    create_limit(client, food["id"], amount_cents=10_000)
    create_transaction(client, food["id"], amount_cents=1_000, date="2026-10-10")
    buy(client, food, card, 1_000)
    assert limit_in(client)["will_exceed"] is True
    assert limit_in(client, "2026-11")["will_exceed"] is False


def test_editing_the_limit_resets_alerts_of_this_month_and_the_next_two(client, db, food, card):
    limit = create_limit(client, food["id"], amount_cents=10_000)
    buy(client, food, card, 9_500)
    alerts(client)
    response = client.put(f"/api/limits/{limit['id']}", json={"amount_cents": 50_000})
    assert response.status_code == 200, response.text
    assert db.scalars(select(LimitAlert.month).where(LimitAlert.limit_id == limit["id"])).all() == []


def test_percent_limit_uses_the_planned_income_of_the_month_asked(client, food):
    salary = create_income_category(client)
    create_transaction(client, salary["id"], kind="income", amount_cents=100_000, date="2026-11-05")
    create_limit(client, food["id"], amount_cents=None, income_percent=10)
    november = limit_in(client, "2026-11")
    assert (november["amount_cents"], november["income_cents"]) == (10_000, 100_000)
    assert limit_in(client)["no_income"] is True


def test_editing_the_card_moves_purchases_but_keeps_recorded_alerts(client, food, card):
    create_limit(client, food["id"], amount_cents=10_000)
    buy(client, food, card, 9_500)
    alerts(client)
    # Fechando no dia 26 e vencendo no dia 25, a compra de hoje vence em 25/12: dezembro.
    changed = {**card_fields(card), "closing_day": 26, "due_day": 25}
    response = client.put(f"/api/cards/{card['id']}", json=changed)
    assert response.status_code == 200, response.text
    assert limit_in(client, "2026-11")["spent_cents"] == 0
    assert limit_in(client, "2026-12")["spent_cents"] == 9_500
    assert ("reached_90", "2026-11") in [(item["kind"], item["month"]) for item in alerts(client)]


def card_fields(card: dict) -> dict:
    return {key: card[key] for key in ("name", "limit_cents", "closing_day", "due_day")}


# Revisão final (rodada 6)


def test_browsing_a_past_month_does_not_record_alerts(client, db, food):
    create_limit(client, food["id"], amount_cents=10_000)
    create_transaction(client, food["id"], amount_cents=20_000, date="2026-08-10")
    assert limit_in(client, "2026-08")["spent_cents"] == 20_000
    assert db.scalars(select(LimitAlert.month)).all() == []


def test_editing_the_card_of_a_purchase_uses_the_new_card(client, db, food, card):
    other = create_card(
        client, name="Fecha 26", closing_day=26, due_day=25
    )  # a compra de hoje vence em 25/12
    create_limit(client, food["id"], amount_cents=10_000)
    purchase = buy(client, food, card, 1_000)
    response = client.put(
        f"/api/transactions/{purchase['id']}",
        json={**editable(purchase), "card_id": other["id"], "amount_cents": 9_500},
    )
    assert response.status_code == 200, response.text
    assert response.json()["payment_month"] == "2026-12"
    assert set(db.scalars(select(LimitAlert.month)).all()) == {date(2026, 12, 1)}  # 50% (silencioso) e 90%


def test_editing_pix_into_card_uses_the_card(client, db, food, card):
    create_limit(client, food["id"], amount_cents=10_000)
    purchase = create_transaction(client, food["id"], amount_cents=1_000, date="2026-10-27")
    response = client.put(
        f"/api/transactions/{purchase['id']}",
        json={
            **editable(purchase),
            "payment_method": "credit_card",
            "card_id": card["id"],
            "amount_cents": 9_500,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["payment_month"] == "2026-11"
    assert set(db.scalars(select(LimitAlert.month)).all()) == {date(2026, 11, 1)}  # 50% (silencioso) e 90%


def test_other_user_sees_none_of_my_limits_in_any_month(client, other_client, food, card):
    create_limit(client, food["id"], amount_cents=10_000)
    buy(client, food, card, 9_500)
    for month in ("2026-10", "2026-11"):
        response = other_client.get("/api/limits", params={"month": month})
        assert response.status_code == 200, response.text
        assert response.json() == []


def editable(transaction: dict) -> dict:
    fields = (
        "description",
        "kind",
        "amount_cents",
        "date",
        "category_id",
        "payment_method",
        "card_id",
        "notes",
    )
    return {key: transaction[key] for key in fields}
