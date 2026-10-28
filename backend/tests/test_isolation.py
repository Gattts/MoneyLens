"""Um usuário nunca vê nem altera os dados de outro (o item alheio responde como se não existisse)."""

import pytest

from tests.factories import create_card, create_category, create_goal, create_recurring


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
