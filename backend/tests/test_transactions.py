import pytest

from tests.factories import (
    create_card,
    create_category,
    create_goal,
    create_income_category,
    create_transaction,
    create_transactions,
)


@pytest.fixture
def needs(client):
    return create_category(client)


@pytest.fixture
def card(client):
    return create_card(client)


def _post(client, payload):
    base = {
        "description": "Compra",
        "kind": "expense",
        "amount_cents": 10_000,
        "date": "2026-10-05",
        "payment_method": "pix",
    }
    return client.post("/api/transactions", json=base | payload)


def _errors(response):
    assert response.status_code == 422, response.text
    return {error["field"]: error["message"] for error in response.json()["errors"]}


def test_expense_takes_the_budget_group_of_its_category(client, needs):
    transaction = create_transaction(client, needs["id"])
    assert (transaction["bucket"], transaction["amount_cents"], transaction["date"]) == (
        "needs",
        10_000,
        "2026-10-05",
    )


def test_budget_group_can_be_overridden_per_transaction(client, needs):
    assert create_transaction(client, needs["id"], bucket="wants")["bucket"] == "wants"


def test_income_has_no_budget_group(client):
    salary = create_income_category(client)
    assert create_transaction(client, salary["id"], kind="income")["bucket"] is None
    assert "bucket" in _errors(
        _post(client, {"kind": "income", "category_id": salary["id"], "bucket": "needs"})
    )


def test_category_must_exist_match_the_kind_and_be_active(client, needs):
    salary = create_income_category(client)
    assert _errors(_post(client, {"category_id": 999})) == {"category_id": "Categoria não encontrada."}
    assert _errors(_post(client, {"category_id": salary["id"]})) == {
        "category_id": "Escolha uma categoria de despesa."
    }
    client.put(
        f"/api/categories/{needs['id']}",
        json={"name": "Mercado", "kind": "expense", "default_bucket": "needs", "archived": True},
    )
    assert "arquivada" in _errors(_post(client, {"category_id": needs["id"]}))["category_id"]


def test_card_rules_follow_the_payment_method(client, needs, card):
    salary = create_income_category(client)
    assert _errors(_post(client, {"category_id": needs["id"], "payment_method": "credit_card"})) == {
        "card_id": "Escolha o cartão."
    }
    assert "card_id" in _errors(_post(client, {"category_id": needs["id"], "card_id": card["id"]}))
    income_on_card = _post(
        client,
        {
            "kind": "income",
            "category_id": salary["id"],
            "payment_method": "credit_card",
            "card_id": card["id"],
        },
    )
    assert "payment_method" in _errors(income_on_card)


@pytest.mark.parametrize(
    ("amount", "message"),
    [
        ("10,00", "Informe um número inteiro."),
        (10.5, "Informe um número inteiro."),
        (0, "Informe um valor maior que 0."),
        (-500, "Informe um valor maior que 0."),
        (None, "Informe um número inteiro."),
    ],
)
def test_invalid_amounts_are_rejected(client, needs, amount, message):
    assert _errors(_post(client, {"category_id": needs["id"], "amount_cents": amount})) == {
        "amount_cents": message
    }


@pytest.mark.parametrize(
    ("day", "message"),
    [
        ("2026-02-30", "Data inválida. Use o formato AAAA-MM-DD."),
        ("30/10/2026", "Data inválida. Use o formato AAAA-MM-DD."),
        ("1999-12-31", "Use uma data entre 01/01/2000 e 31/12/2100."),
        (1767225600, "Data inválida. Use o formato AAAA-MM-DD."),  # timestamp de 2026-01-01
    ],
)
def test_invalid_dates_are_rejected(client, needs, day, message):
    assert _errors(_post(client, {"category_id": needs["id"], "date": day})) == {"date": message}


def test_missing_and_blank_fields_are_reported_together(client, needs):
    response = client.post("/api/transactions", json={"description": "  ", "category_id": needs["id"]})
    errors = _errors(response)
    assert errors["description"] == "Preencha este campo."
    assert errors["kind"] == errors["amount_cents"] == errors["date"] == "Campo obrigatório."


def test_installments_split_the_total_across_monthly_invoices(client, needs, card):
    created = create_transactions(
        client,
        needs["id"],
        description="Notebook",
        amount_cents=100,
        date="2026-01-31",
        payment_method="credit_card",
        card_id=card["id"],
        installments=3,
    )
    assert [(t["amount_cents"], t["date"], t["installment_number"]) for t in created] == [
        (34, "2026-01-31", 1),
        (33, "2026-02-28", 2),
        (33, "2026-03-31", 3),
    ]
    assert len({t["installment_group"] for t in created}) == 1
    assert {t["installment_total"] for t in created} == {3}


@pytest.mark.parametrize("method", ["cash", "debit", "transfer"])
def test_installments_only_on_card_pix_and_bank_slip(client, needs, method):
    payload = {"category_id": needs["id"], "installments": 3, "payment_method": method}
    assert _errors(_post(client, payload)) == {
        "installments": "Parcelamento só existe no cartão de crédito, no Pix e no boleto."
    }


@pytest.mark.parametrize("method", ["pix", "bank_slip"])
def test_pix_and_bank_slip_accept_installments(client, needs, method):
    response = _post(client, {"category_id": needs["id"], "installments": 3, "payment_method": method})
    assert response.status_code == 201, response.text
    created = response.json()
    assert [(t["amount_cents"], t["date"], t["installment_number"], t["card_id"]) for t in created] == [
        (3334, "2026-10-05", 1, None),
        (3333, "2026-11-05", 2, None),
        (3333, "2026-12-05", 3, None),
    ]
    assert {t["payment_method"] for t in created} == {method}


def test_installment_count_and_value_limits(client, needs, card):
    on_card = {"category_id": needs["id"], "payment_method": "credit_card", "card_id": card["id"]}
    assert _errors(_post(client, on_card | {"installments": 49})) == {
        "installments": "Informe um valor até 48."
    }
    assert "amount_cents" in _errors(_post(client, on_card | {"amount_cents": 2, "installments": 3}))


def test_goal_link_requires_a_savings_expense(client, needs):
    goal = create_goal(client)
    invest = create_category(client, name="Investimentos", default_bucket="savings")
    assert "goal_id" in _errors(_post(client, {"category_id": needs["id"], "goal_id": goal["id"]}))
    linked = create_transaction(client, invest["id"], goal_id=goal["id"])
    assert (linked["bucket"], linked["goal_id"]) == ("savings", goal["id"])


def test_list_filters_by_month_and_orders_by_most_recent(client, needs):
    first = create_transaction(client, needs["id"], date="2026-10-01")
    last = create_transaction(client, needs["id"], date="2026-10-20")
    create_transaction(client, needs["id"], date="2026-11-01")
    listed = client.get("/api/transactions", params={"month": "2026-10"}).json()
    assert [t["id"] for t in listed] == [last["id"], first["id"]]


def test_list_filters_by_text_kind_category_and_card(client, needs, card):
    leisure = create_category(client, name="Lazer", default_bucket="wants")
    salary = create_income_category(client)
    cinema = create_transaction(client, leisure["id"], description="Cinema com amigos")
    on_card = create_transaction(client, needs["id"], payment_method="credit_card", card_id=card["id"])
    pay = create_transaction(client, salary["id"], kind="income")

    def ids(**params):
        return [t["id"] for t in client.get("/api/transactions", params=params).json()]

    assert ids(q="CINEMA") == [cinema["id"]]
    assert ids(kind="income") == [pay["id"]]
    assert ids(category_id=leisure["id"]) == [cinema["id"]]
    assert ids(card_id=card["id"]) == [on_card["id"]]


def test_search_treats_wildcards_as_plain_text(client, needs):
    discount = create_transaction(client, needs["id"], description="Cupom 50% off")
    create_transaction(client, needs["id"], description="Feira")
    assert [t["id"] for t in client.get("/api/transactions", params={"q": "%"}).json()] == [discount["id"]]


def test_invalid_month_filter_is_rejected(client):
    response = client.get("/api/transactions", params={"month": "2026-13"})
    assert _errors(response) == {"month": "Mês inválido. Use o formato AAAA-MM, entre 2000 e 2100."}


def test_update_transaction(client, needs):
    transaction = create_transaction(client, needs["id"])
    payload = {
        "description": "Compra corrigida",
        "kind": "expense",
        "amount_cents": 12_345,
        "date": "2026-10-06",
        "category_id": needs["id"],
        "payment_method": "debit",
    }
    response = client.put(f"/api/transactions/{transaction['id']}", json=payload)
    assert response.status_code == 200
    assert (response.json()["amount_cents"], response.json()["payment_method"]) == (12_345, "debit")
    missing = client.put("/api/transactions/999", json=payload)
    assert (missing.status_code, missing.json()["detail"]) == (404, "Lançamento não encontrado.")


def test_editing_keeps_an_archived_category_that_was_already_set(client, needs):
    transaction = create_transaction(client, needs["id"])
    client.put(
        f"/api/categories/{needs['id']}",
        json={"name": "Mercado", "kind": "expense", "default_bucket": "needs", "archived": True},
    )
    payload = {k: transaction[k] for k in ("kind", "amount_cents", "date", "category_id", "payment_method")}
    response = client.put(
        f"/api/transactions/{transaction['id']}", json=payload | {"description": "Novo nome"}
    )
    assert response.status_code == 200


def test_installment_cannot_move_to_another_payment_method(client, needs, card):
    first = create_transactions(
        client, needs["id"], payment_method="credit_card", card_id=card["id"], installments=2
    )[0]
    payload = {k: first[k] for k in ("description", "kind", "amount_cents", "date", "category_id")}
    response = client.put(f"/api/transactions/{first['id']}", json=payload | {"payment_method": "pix"})
    assert "payment_method" in _errors(response)


def test_update_rejects_installment_field(client, needs):
    transaction = create_transaction(client, needs["id"])
    payload = {k: transaction[k] for k in ("description", "kind", "amount_cents", "date", "category_id")}
    response = client.put(
        f"/api/transactions/{transaction['id']}", json=payload | {"payment_method": "pix", "installments": 2}
    )
    assert _errors(response) == {"installments": "Campo não permitido."}


def test_delete_one_installment_or_the_whole_purchase(client, needs, card):
    installments = create_transactions(
        client, needs["id"], payment_method="credit_card", card_id=card["id"], installments=3
    )
    assert client.delete(f"/api/transactions/{installments[0]['id']}").status_code == 204
    assert len(client.get("/api/transactions").json()) == 2
    response = client.delete(f"/api/transactions/{installments[1]['id']}", params={"scope": "installments"})
    assert response.status_code == 204
    assert client.get("/api/transactions").json() == []
    assert client.delete("/api/transactions/999").status_code == 404
