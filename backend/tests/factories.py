"""Atalhos para criar dados pela API nos testes. Cada função falha o teste se a API recusar."""

from typing import Any


def _post(client, url: str, payload: dict[str, Any]) -> Any:
    response = client.post(url, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def create_category(client, **overrides: Any) -> dict[str, Any]:
    payload = {"name": "Mercado", "icon": "🛒", "kind": "expense", "default_bucket": "needs"}
    return _post(client, "/api/categories", payload | overrides)


def create_income_category(client, **overrides: Any) -> dict[str, Any]:
    return create_category(
        client, **({"name": "Salário", "kind": "income", "default_bucket": None} | overrides)
    )


def create_card(client, **overrides: Any) -> dict[str, Any]:
    payload = {"name": "Nubank", "limit_cents": 300_000, "closing_day": 10, "due_day": 17}
    return _post(client, "/api/cards", payload | overrides)


def create_goal(client, **overrides: Any) -> dict[str, Any]:
    payload = {"name": "Reserva de emergência", "icon": "🛟", "target_cents": 1_000_000}
    return _post(client, "/api/goals", payload | overrides)


def create_transactions(client, category_id: int, **overrides: Any) -> list[dict[str, Any]]:
    payload = {
        "description": "Compra do mês",
        "kind": "expense",
        "amount_cents": 10_000,
        "date": "2026-10-05",
        "category_id": category_id,
        "payment_method": "pix",
    }
    return _post(client, "/api/transactions", payload | overrides)


def create_transaction(client, category_id: int, **overrides: Any) -> dict[str, Any]:
    created = create_transactions(client, category_id, **overrides)
    assert len(created) == 1
    return created[0]


def create_recurring(client, category_id: int, **overrides: Any) -> dict[str, Any]:
    payload = {
        "description": "Aluguel",
        "kind": "expense",
        "amount_cents": 150_000,
        "category_id": category_id,
        "day_of_month": 10,
        "payment_method": "bank_slip",
        "start_month": "2026-01",
    }
    return _post(client, "/api/recurring", payload | overrides)


def create_limit(client, category_id: int, **overrides: Any) -> dict[str, Any]:
    return _post(client, "/api/limits", {"category_id": category_id, "amount_cents": 30_000} | overrides)
