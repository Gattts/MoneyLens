"""Um usuário nunca vê nem altera os dados de outro (o item alheio responde como se não existisse)."""

import pytest

from tests.factories import create_card, create_category, create_goal, create_recurring, create_transactions
from tests.invoice_samples import LOJA, UBER, invoice_pdf, upload


@pytest.fixture
def mine(client) -> dict[str, dict]:
    """Um cadastro completo do usuário principal (ana)."""
    category = create_category(client, name="Pets", default_bucket="wants")
    rule = client.post(
        "/api/category-rules",
        json={"pattern": "PADARIA", "match_type": "contains", "category_id": category["id"]},
    )
    assert rule.status_code == 201, rule.text
    return {
        "category": category,
        "card": create_card(client, name="Inter"),
        "goal": create_goal(client, name="Viagem"),
        "recurring": create_recurring(client, category["id"]),
        "rule": rule.json(),
    }


CATALOG_LISTS = {
    "/api/categories": "category",
    "/api/cards": "card",
    "/api/goals": "goal",
    "/api/recurring": "recurring",
    "/api/category-rules": "rule",
}


def test_other_user_sees_none_of_my_catalog(mine, other_client):
    for url, kind in CATALOG_LISTS.items():
        ids = {item["id"] for item in other_client.get(url).json()}
        assert mine[kind]["id"] not in ids, url


def test_other_user_gets_404_on_my_items(mine, other_client):
    category, card, goal = mine["category"], mine["card"], mine["goal"]
    recurring, rule = mine["recurring"], mine["rule"]
    attempts = [
        (
            "put",
            f"/api/categories/{category['id']}",
            {"name": "X", "kind": "expense", "default_bucket": "wants"},
        ),
        ("delete", f"/api/categories/{category['id']}", None),
        ("put", f"/api/cards/{card['id']}", {"name": "X", "limit_cents": 1, "closing_day": 1, "due_day": 2}),
        ("delete", f"/api/cards/{card['id']}", None),
        ("get", f"/api/cards/{card['id']}/invoice", None),
        ("delete", f"/api/cards/{card['id']}/invoice-password", None),
        ("put", f"/api/goals/{goal['id']}", {"name": "X", "target_cents": 1}),
        ("delete", f"/api/goals/{goal['id']}", None),
        ("delete", f"/api/recurring/{recurring['id']}", None),
        ("post", f"/api/recurring/{recurring['id']}/confirm", {"month": "2026-10"}),
        (
            "put",
            f"/api/category-rules/{rule['id']}",
            {"pattern": "X1", "match_type": "exact", "category_id": 1},
        ),
        ("delete", f"/api/category-rules/{rule['id']}", None),
    ]
    for method, url, body in attempts:
        response = getattr(other_client, method)(url, **({"json": body} if body is not None else {}))
        assert response.status_code == 404, (method, url, response.status_code)


def test_other_user_cannot_reference_my_category(mine, other_client):
    response = other_client.post(
        "/api/recurring",
        json={
            "description": "Aluguel",
            "kind": "expense",
            "amount_cents": 1000,
            "category_id": mine["category"]["id"],
            "day_of_month": 10,
            "payment_method": "pix",
            "start_month": "2026-01",
        },
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "category_id", "message": "Categoria não encontrada."}]


def test_names_are_unique_per_user(client, other_client):
    assert create_category(client, name="Pets", default_bucket="wants")["name"] == "Pets"
    assert create_category(other_client, name="Pets", default_bucket="wants")["name"] == "Pets"
    assert create_card(client, name="Nubank")["name"] == create_card(other_client, name="Nubank")["name"]


def test_budget_is_per_user(client, other_client):
    assert (
        client.put(
            "/api/budget-settings", json={"needs_pct": 60, "wants_pct": 20, "savings_pct": 20}
        ).status_code
        == 200
    )
    assert other_client.get("/api/budget-settings").json() == {
        "needs_pct": 50,
        "wants_pct": 30,
        "savings_pct": 20,
    }


# Como cada rota isola os dados. Uma rota nova precisa entrar aqui (o teste de cobertura falha sem ela).
ROUTE_CASES: dict[tuple[str, str], str] = {
    ("POST", "/api/auth/login"): "pública",
    ("POST", "/api/auth/activate"): "pública",
    ("POST", "/api/auth/logout"): "só a própria sessão",
    ("GET", "/api/auth/me"): "só a própria sessão",
    ("GET", "/api/budget-settings"): "do usuário (test_budget_is_per_user)",
    ("PUT", "/api/budget-settings"): "do usuário (test_budget_is_per_user)",
    ("GET", "/api/cards"): "lista filtrada",
    ("POST", "/api/cards"): "cria com o dono da sessão",
    ("PUT", "/api/cards/{item_id}"): "404",
    ("DELETE", "/api/cards/{item_id}"): "404",
    ("GET", "/api/cards/{item_id}/invoice"): "404",
    ("DELETE", "/api/cards/{item_id}/invoice-password"): "404",
    ("GET", "/api/categories"): "lista filtrada",
    ("POST", "/api/categories"): "cria com o dono da sessão",
    ("PUT", "/api/categories/{item_id}"): "404",
    ("DELETE", "/api/categories/{item_id}"): "404",
    ("GET", "/api/category-rules"): "lista filtrada",
    ("POST", "/api/category-rules"): "422 com categoria alheia",
    ("PUT", "/api/category-rules/{item_id}"): "404",
    ("DELETE", "/api/category-rules/{item_id}"): "404",
    ("GET", "/api/goals"): "lista filtrada",
    ("POST", "/api/goals"): "cria com o dono da sessão",
    ("PUT", "/api/goals/{item_id}"): "404",
    ("DELETE", "/api/goals/{item_id}"): "404",
    ("GET", "/api/invoice-imports"): "lista filtrada",
    ("POST", "/api/invoice-imports"): "422 com cartão alheio",
    ("GET", "/api/invoice-imports/{item_id}"): "404",
    ("DELETE", "/api/invoice-imports/{item_id}"): "404",
    ("POST", "/api/invoice-imports/{item_id}/confirm"): "404",
    ("PUT", "/api/invoice-lines/{item_id}"): "404",
    ("POST", "/api/invoice-lines/{item_id}/include"): "404",
    ("GET", "/api/recurring"): "lista filtrada",
    ("POST", "/api/recurring"): "422 com categoria alheia",
    ("PUT", "/api/recurring/{item_id}"): "404",
    ("DELETE", "/api/recurring/{item_id}"): "404",
    ("POST", "/api/recurring/{item_id}/confirm"): "404",
    ("GET", "/api/summary/month"): "totais só do usuário",
    ("GET", "/api/summary/year"): "totais só do usuário",
    ("GET", "/api/transactions"): "lista filtrada",
    ("POST", "/api/transactions"): "422 com categoria/cartão/meta alheios",
    ("PUT", "/api/transactions/{item_id}"): "404",
    ("DELETE", "/api/transactions/{item_id}"): "404",
    ("GET", "/api/admin/users"): "só administradores",
    ("POST", "/api/admin/users"): "só administradores",
    ("POST", "/api/admin/users/{item_id}/invite"): "só administradores",
    ("DELETE", "/api/admin/users/{item_id}"): "só administradores",
}


def test_every_route_is_covered_by_the_isolation_cases(app):
    routes = {(method.upper(), path) for path, item in app.openapi()["paths"].items() for method in item}
    assert routes == set(ROUTE_CASES), "rota nova: diga em ROUTE_CASES como ela isola os dados"


def test_other_user_cannot_touch_my_money(client, other_client, card, transport):
    parcels = create_transactions(
        client,
        transport["id"],
        description="Notebook",
        amount_cents=20000,
        date="2026-09-10",
        payment_method="credit_card",
        card_id=card["id"],
        installments=2,
    )
    imported = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    pending = next(line for line in imported["lines"] if line["status"] == "pending")

    assert other_client.get("/api/transactions", params={"month": "2026-09"}).json() == []
    assert (
        other_client.get("/api/summary/month", params={"month": "2026-09"}).json()["needs"]["total_cents"]
        == 0
    )
    assert other_client.get("/api/invoice-imports").json()["imports"] == []
    full_body = {
        "description": "Notebook",
        "kind": "expense",
        "amount_cents": 20000,
        "date": "2026-09-10",
        "category_id": transport["id"],
        "payment_method": "credit_card",
        "card_id": card["id"],
    }
    attempts = [
        ("put", f"/api/transactions/{parcels[0]['id']}", full_body),
        ("delete", f"/api/transactions/{parcels[0]['id']}", None),
        ("get", f"/api/invoice-imports/{imported['id']}", None),
        ("post", f"/api/invoice-imports/{imported['id']}/confirm", None),
        ("delete", f"/api/invoice-imports/{imported['id']}", None),
        ("put", f"/api/invoice-lines/{pending['id']}", {"category_id": transport["id"], "remember": False}),
        ("post", f"/api/invoice-lines/{pending['id']}/include", None),
    ]
    for method, url, body in attempts:
        response = getattr(other_client, method)(url, **({"json": body} if body is not None else {}))
        assert response.status_code == 404, (method, url, response.status_code)

    refused = upload(other_client, card["id"], invoice_pdf(UBER, LOJA))
    assert refused.json()["errors"] == [{"field": "card_id", "message": "Cartão não encontrado."}]
    assert (
        client.get("/api/transactions", params={"month": "2026-09"}).json() != []
    )  # nada do que é meu sumiu


def test_learned_rule_does_not_touch_other_users_lines(client, other_client, card, transport):
    other_card = create_card(other_client, name="Inter")
    leisure = create_category(client, name="Lazer", default_bucket="wants")
    mine = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    theirs = upload(other_client, other_card["id"], invoice_pdf(UBER, LOJA)).json()
    my_line = next(line for line in mine["lines"] if line["description"] == "LOJA NOVA")
    client.put(f"/api/invoice-lines/{my_line['id']}", json={"category_id": leisure["id"], "remember": True})
    their_line = next(
        line
        for line in other_client.get(f"/api/invoice-imports/{theirs['id']}").json()["lines"]
        if line["description"] == "LOJA NOVA"
    )
    assert their_line["status"] == "pending"


def test_other_user_gets_404_editing_my_recurring(mine, other_client):
    body = {
        "description": "Aluguel",
        "kind": "expense",
        "amount_cents": 1000,
        "category_id": mine["category"]["id"],
        "day_of_month": 10,
        "payment_method": "pix",
        "start_month": "2026-01",
    }
    assert other_client.put(f"/api/recurring/{mine['recurring']['id']}", json=body).status_code == 404


def test_other_user_cannot_use_my_category_card_or_goal_in_a_transaction(mine, other_client):
    own_category = create_category(other_client, name="Minha", default_bucket="savings")
    base = {
        "description": "Compra",
        "kind": "expense",
        "amount_cents": 1000,
        "date": "2026-10-05",
        "category_id": own_category["id"],
        "payment_method": "pix",
    }
    attempts = {
        "category_id": ({"category_id": mine["category"]["id"]}, "Categoria não encontrada."),
        "card_id": (
            {"payment_method": "credit_card", "card_id": mine["card"]["id"]},
            "Cartão não encontrado.",
        ),
        "goal_id": ({"goal_id": mine["goal"]["id"]}, "Meta não encontrada."),
    }
    for field, (change, message) in attempts.items():
        response = other_client.post("/api/transactions", json=base | change)
        assert response.status_code == 422, (field, response.text)
        assert response.json()["errors"] == [{"field": field, "message": message}]
