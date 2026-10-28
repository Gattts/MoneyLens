import pytest

from financeiro.routers import recurring as recurring_router
from tests.factories import create_card, create_category, create_income_category, create_recurring


@pytest.fixture
def housing(client):
    return create_category(client, name="Moradia")


def _errors(response):
    assert response.status_code == 422, response.text
    return {error["field"]: error["message"] for error in response.json()["errors"]}


RULE = {
    "description": "Aluguel",
    "kind": "expense",
    "amount_cents": 150_000,
    "day_of_month": 10,
    "payment_method": "bank_slip",
    "start_month": "2026-01",
}


def test_create_and_list_rules(client, housing):
    rule = create_recurring(client, housing["id"], end_month="2026-12")
    assert (rule["bucket"], rule["start_month"], rule["end_month"]) == ("needs", "2026-01", "2026-12")
    assert [r["id"] for r in client.get("/api/recurring").json()] == [rule["id"]]


def test_rule_validation(client, housing):
    base = RULE | {"category_id": housing["id"]}
    assert _errors(
        client.post("/api/recurring", json=base | {"start_month": "2026-05", "end_month": "2026-04"})
    ) == {"end_month": "O mês final precisa ser igual ou posterior ao mês inicial."}
    assert "start_month" in _errors(client.post("/api/recurring", json=base | {"start_month": "2026-1"}))
    assert "day_of_month" in _errors(client.post("/api/recurring", json=base | {"day_of_month": 32}))
    assert _errors(client.post("/api/recurring", json=base | {"payment_method": "credit_card"})) == {
        "card_id": "Escolha o cartão."
    }


def test_rule_on_credit_card(client, housing):
    card = create_card(client)
    rule = create_recurring(client, housing["id"], payment_method="credit_card", card_id=card["id"])
    assert rule["card_id"] == card["id"]


def test_update_and_delete_rule(client, housing):
    rule = create_recurring(client, housing["id"])
    updated = client.put(
        f"/api/recurring/{rule['id']}", json=RULE | {"category_id": housing["id"], "amount_cents": 160_000}
    )
    assert updated.json()["amount_cents"] == 160_000
    missing = client.put("/api/recurring/999", json=RULE | {"category_id": housing["id"]})
    assert (missing.status_code, missing.json()["detail"]) == (404, "Fixa não encontrada.")
    assert client.delete(f"/api/recurring/{rule['id']}").status_code == 204


def test_confirm_creates_the_transaction_of_the_month(client, housing):
    rule = create_recurring(client, housing["id"])
    response = client.post(f"/api/recurring/{rule['id']}/confirm", json={"month": "2026-10"})
    assert response.status_code == 201
    transaction = response.json()
    assert (transaction["date"], transaction["amount_cents"], transaction["description"]) == (
        "2026-10-10",
        150_000,
        "Aluguel",
    )
    assert (transaction["recurring_rule_id"], transaction["recurrence_month"]) == (rule["id"], "2026-10")


def test_confirm_with_the_amount_actually_paid(client):
    salary = create_income_category(client)
    rule = create_recurring(client, salary["id"], kind="income", payment_method="transfer", day_of_month=31)
    response = client.post(
        f"/api/recurring/{rule['id']}/confirm", json={"month": "2026-02", "amount_cents": 160_000}
    )
    assert (response.json()["date"], response.json()["amount_cents"]) == ("2026-02-28", 160_000)


def test_double_confirmation_is_rejected(client, housing):
    rule = create_recurring(client, housing["id"])
    url = f"/api/recurring/{rule['id']}/confirm"
    assert client.post(url, json={"month": "2026-10"}).status_code == 201
    second = client.post(url, json={"month": "2026-10"})
    assert second.status_code == 409
    assert second.json()["detail"] == "Esta fixa já foi confirmada em 10/2026."
    assert len(client.get("/api/transactions", params={"month": "2026-10"}).json()) == 1


def test_cannot_confirm_a_month_outside_the_rule(client, housing):
    rule = create_recurring(client, housing["id"], start_month="2026-03", end_month="2026-05")
    url = f"/api/recurring/{rule['id']}/confirm"
    assert _errors(client.post(url, json={"month": "2026-02"})) == {
        "month": "Esta fixa não acontece nesse mês."
    }
    assert "month" in _errors(client.post(url, json={"month": "2026-06"}))


def test_deleting_a_rule_keeps_confirmed_transactions(client, housing):
    rule = create_recurring(client, housing["id"])
    client.post(f"/api/recurring/{rule['id']}/confirm", json={"month": "2026-10"})
    client.delete(f"/api/recurring/{rule['id']}")
    transactions = client.get("/api/transactions").json()
    assert [(t["description"], t["recurring_rule_id"]) for t in transactions] == [("Aluguel", None)]


def test_simultaneous_confirmations_get_the_friendly_message(client, housing, monkeypatch):
    # Dois cliques quase juntos passam pela checagem antes de qualquer um gravar: quem barra é o banco.
    rule = create_recurring(client, housing["id"])
    real_check = recurring_router._already_confirmed
    window = {"open": True}

    def racing_check(*args):
        # Na janela da corrida, a 1ª checagem de cada requisição ainda não vê a outra gravação.
        if window["open"]:
            window["open"] = False
            return False
        return real_check(*args)

    monkeypatch.setattr(recurring_router, "_already_confirmed", racing_check)
    url = f"/api/recurring/{rule['id']}/confirm"
    assert client.post(url, json={"month": "2026-10"}).status_code == 201
    window["open"] = True
    second = client.post(url, json={"month": "2026-10"})
    assert (second.status_code, second.json()["detail"]) == (409, "Esta fixa já foi confirmada em 10/2026.")
