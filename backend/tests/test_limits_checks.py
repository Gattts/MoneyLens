"""A conferência dos tetos roda depois de cada ação que muda despesas (os alertas são lidos direto do banco,
porque a leitura pela API também confere)."""

import pytest
from sqlalchemy import select

from financeiro.models import LimitAlert
from financeiro.services import limits
from tests.factories import (
    create_category,
    create_limit,
    create_recurring,
    create_transaction,
    create_transactions,
)
from tests.statement_samples import Day, pix_out, statement_pages, statement_pdf, upload_statement

FIFTY = {("reached_50", False)}
TRANSACTION_FIELDS = ("description", "kind", "amount_cents", "date", "category_id", "payment_method")


class Spy:
    def __init__(self) -> None:
        self.calls: list[int] = []

    def __call__(self, session, user_id, today) -> None:
        self.calls.append(user_id)


@pytest.fixture(autouse=True)
def no_forecast(monkeypatch):
    monkeypatch.setattr(limits, "forecast_p50", lambda *args: {})


@pytest.fixture
def food(client) -> dict:
    return create_category(client, name="Comida fora")


@pytest.fixture
def food_limit(client, food) -> dict:
    return create_limit(client, food["id"], amount_cents=30_000)


def alert_kinds(db) -> set[tuple[str, bool]]:
    db.expire_all()
    return {(alert.kind.value, alert.silent) for alert in db.scalars(select(LimitAlert))}


def spy_on(monkeypatch, target: str) -> Spy:
    spy = Spy()
    monkeypatch.setattr(target, spy)
    return spy


def edit(client, transaction: dict, **changes) -> None:
    body = {field: transaction[field] for field in TRANSACTION_FIELDS} | changes
    assert client.put(f"/api/transactions/{transaction['id']}", json=body).status_code == 200


def statement(client, *entries) -> dict:
    response = upload_statement(
        client, statement_pdf(statement_pages([Day("02 OUT 2026", outflows=list(entries))]))
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_creating_a_transaction_checks(client, db, food, food_limit):
    create_transaction(client, food["id"], amount_cents=15_000, date="2026-10-20")
    assert alert_kinds(db) == FIFTY


def test_installments_check(client, db, card, food, food_limit):
    on_card = {"payment_method": "credit_card", "card_id": card["id"], "installments": 2}
    create_transactions(client, food["id"], amount_cents=30_000, date="2026-10-10", **on_card)
    assert alert_kinds(db) == FIFTY


def test_editing_a_transaction_checks(client, db, food, food_limit):
    transaction = create_transaction(client, food["id"], amount_cents=10_000, date="2026-10-20")
    assert alert_kinds(db) == set()
    edit(client, transaction, amount_cents=15_000)
    assert alert_kinds(db) == FIFTY


def test_moving_a_transaction_into_the_category_checks(client, db, food, food_limit):
    other = create_category(client, name="Mercado")
    transaction = create_transaction(client, other["id"], amount_cents=15_000, date="2026-10-20")
    edit(client, transaction, category_id=food["id"])
    assert alert_kinds(db) == FIFTY


def test_confirming_a_recurring_occurrence_checks(client, db, food, food_limit):
    rule = create_recurring(client, food["id"], amount_cents=15_000, day_of_month=5, payment_method="pix")
    response = client.post(f"/api/recurring/{rule['id']}/confirm", json={"month": "2026-10"})
    assert response.status_code == 201, response.text
    assert alert_kinds(db) == FIFTY


def test_confirming_a_recurring_occurrence_twice_still_says_already_confirmed(client, food, food_limit):
    rule = create_recurring(client, food["id"], amount_cents=15_000, day_of_month=5, payment_method="pix")
    assert client.post(f"/api/recurring/{rule['id']}/confirm", json={"month": "2026-10"}).status_code == 201
    again = client.post(f"/api/recurring/{rule['id']}/confirm", json={"month": "2026-10"})
    assert again.status_code == 409


def test_confirming_a_statement_checks(client, db, food):
    rule = {"pattern": "PADARIA", "match_type": "contains", "category_id": food["id"]}
    assert client.post("/api/category-rules", json=rule).status_code == 201
    create_limit(client, food["id"], amount_cents=2_000)
    imported = statement(client, pix_out("PADARIA", "12,50"))
    assert client.post(f"/api/invoice-imports/{imported['id']}/confirm").status_code == 200
    assert alert_kinds(db) == FIFTY


def test_resolving_a_line_after_confirming_checks(client, db, food):
    create_limit(client, food["id"], amount_cents=2_000)
    imported = statement(client, pix_out("LOJA NOVA", "12,50"))
    assert client.post(f"/api/invoice-imports/{imported['id']}/confirm").status_code == 200
    line = next(line for line in imported["lines"] if line["status"] == "pending")
    body = {"category_id": food["id"], "remember": False}
    assert client.put(f"/api/invoice-lines/{line['id']}", json=body).status_code == 200
    assert alert_kinds(db) == FIFTY


def test_alert_stays_and_does_not_repeat_after_spending_drops(client, db, food, food_limit):
    first = create_transaction(client, food["id"], amount_cents=15_000, date="2026-10-20")
    created_at = db.scalar(select(LimitAlert.created_at))
    assert client.delete(f"/api/transactions/{first['id']}").status_code == 204
    create_transaction(client, food["id"], amount_cents=15_000, date="2026-10-21")
    assert alert_kinds(db) == FIFTY
    assert db.scalar(select(LimitAlert.created_at)) == created_at


def test_users_without_limits_skip_the_forecast(client, food, monkeypatch):
    def fail(*args):
        raise AssertionError("a previsão não devia rodar")

    monkeypatch.setattr(limits, "forecast_p50", fail)
    create_transaction(client, food["id"], amount_cents=15_000, date="2026-10-20")


def test_deleting_a_transaction_checks(client, user, food, monkeypatch):
    transaction = create_transaction(client, food["id"])
    spy = spy_on(monkeypatch, "financeiro.routers.transactions.check_limits")
    assert client.delete(f"/api/transactions/{transaction['id']}").status_code == 204
    assert spy.calls == [user.id]


def test_deleting_the_installment_group_checks(client, user, card, food, monkeypatch):
    on_card = {"payment_method": "credit_card", "card_id": card["id"], "installments": 2}
    [first, _] = create_transactions(client, food["id"], **on_card)
    spy = spy_on(monkeypatch, "financeiro.routers.transactions.check_limits")
    response = client.delete(f"/api/transactions/{first['id']}", params={"scope": "installments"})
    assert response.status_code == 204
    assert spy.calls == [user.id]


def test_undoing_an_import_checks(client, user, monkeypatch):
    imported = statement(client, pix_out("LOJA NOVA", "12,50"))
    assert client.post(f"/api/invoice-imports/{imported['id']}/confirm").status_code == 200
    spy = spy_on(monkeypatch, "financeiro.services.invoices.posting.check_limits")
    assert client.delete(f"/api/invoice-imports/{imported['id']}").status_code == 204
    assert spy.calls == [user.id]


def test_including_a_line_checks(client, user, monkeypatch):
    imported = statement(client, pix_out("LOJA NOVA", "12,50"))
    line = next(line for line in imported["lines"] if line["status"] == "pending")
    assert client.post(f"/api/invoice-lines/{line['id']}/ignore").status_code == 200
    spy = spy_on(monkeypatch, "financeiro.services.invoices.learning.check_limits")
    assert client.post(f"/api/invoice-lines/{line['id']}/include").status_code == 200
    assert spy.calls == [user.id]
