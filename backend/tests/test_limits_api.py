import datetime as dt

import pytest

from financeiro.domain.enums import LimitAlertKind
from financeiro.models import LimitAlert
from financeiro.services import limits
from tests.factories import create_category, create_income_category, create_limit, create_transaction

ONLY_EXPENSE = "Só categorias de despesa ativas têm teto."


@pytest.fixture(autouse=True)
def no_forecast(monkeypatch):
    monkeypatch.setattr(limits, "forecast_p50", lambda *args: {})


def kinds(client) -> list[str]:
    return [item["kind"] for item in client.get("/api/alerts").json()["items"]]


def test_create_list_update_delete(client):
    category = create_category(client, name="Comida fora")
    create_transaction(client, category["id"], amount_cents=10_000, date="2026-10-20")
    created = client.post("/api/limits", json={"category_id": category["id"], "amount_cents": 30_000})
    assert created.status_code == 201, created.text
    [item] = client.get("/api/limits").json()
    assert item | {"id": 0} == {
        "id": 0,
        "category_id": category["id"],
        "name": "Comida fora",
        "icon": category["icon"],
        "amount_cents": 30_000,
        "spent_cents": 10_000,
        "percent": 33,
        "p50_cents": None,
        "will_exceed": False,
        "active": True,
    }
    updated = client.put(f"/api/limits/{item['id']}", json={"amount_cents": 20_000})
    assert (updated.json()["amount_cents"], updated.json()["percent"]) == (20_000, 50)
    assert client.delete(f"/api/limits/{item['id']}").status_code == 204
    assert client.get("/api/limits").json() == []


def test_limit_validation(client):
    income = create_income_category(client)
    archived = create_category(client, name="Antiga", archived=True)
    for category in (income, archived):
        response = client.post("/api/limits", json={"category_id": category["id"], "amount_cents": 1_000})
        assert response.status_code == 422
        assert response.json()["errors"] == [{"field": "category_id", "message": ONLY_EXPENSE}]
    expense = create_category(client)
    create_limit(client, expense["id"])
    duplicate = client.post("/api/limits", json={"category_id": expense["id"], "amount_cents": 1_000})
    assert (duplicate.status_code, duplicate.json()["detail"]) == (409, "Esta categoria já tem teto.")
    zero = client.post("/api/limits", json={"category_id": expense["id"], "amount_cents": 0})
    assert zero.status_code == 422
    missing = client.put("/api/limits/999", json={"amount_cents": 1_000})
    assert (missing.status_code, missing.json()["detail"]) == (404, "Teto não encontrado.")
    assert client.delete("/api/limits/999").status_code == 404
    unknown = client.post("/api/limits", json={"category_id": 999, "amount_cents": 1_000})
    assert (unknown.status_code, unknown.json()["detail"]) == (404, "Categoria não encontrada.")


def test_creating_a_limit_already_passed_gives_one_alert(client):
    category = create_category(client)
    create_transaction(client, category["id"], amount_cents=28_500, date="2026-10-20")
    create_limit(client, category["id"], amount_cents=30_000)
    body = client.get("/api/alerts").json()
    assert body["unread"] == 1
    assert [item["kind"] for item in body["items"]] == ["reached_90"]


def test_changing_the_amount_restarts_the_month(client):
    category = create_category(client)
    create_transaction(client, category["id"], amount_cents=27_000, date="2026-10-20")
    limit = create_limit(client, category["id"], amount_cents=30_000)
    assert kinds(client) == ["reached_90"]
    assert client.put(f"/api/limits/{limit['id']}", json={"amount_cents": 50_000}).status_code == 200
    body = client.get("/api/alerts").json()
    assert ([item["kind"] for item in body["items"]], body["unread"]) == (["reached_50"], 1)


def test_alerts_list_hides_silent_and_keeps_the_20_most_recent(client, db, user):
    category = create_category(client)
    limit = create_limit(client, category["id"])
    start = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
    for index in range(26):
        db.add(
            LimitAlert(
                user_id=user.id,
                limit_id=limit["id"],
                month=dt.date(2024 + index // 12, index % 12 + 1, 1),
                kind=LimitAlertKind.REACHED_50,
                spent_cents=15_000,
                limit_cents=30_000,
                silent=index == 25,  # o mais recente é silencioso
                created_at=start + dt.timedelta(minutes=index),
            )
        )
    db.commit()
    body = client.get("/api/alerts").json()
    assert (len(body["items"]), body["unread"]) == (20, 25)
    assert body["items"][0]["month"] == "2026-01"  # índice 24
    assert body["items"][0] | {"id": 0, "created_at": ""} == {
        "id": 0,
        "kind": "reached_50",
        "category_id": category["id"],
        "name": category["name"],
        "icon": category["icon"],
        "spent_cents": 15_000,
        "limit_cents": 30_000,
        "forecast_cents": None,
        "month": "2026-01",
        "created_at": "",
        "read_at": None,
    }


def test_read_marks_given_ids_or_all(client):
    first = create_category(client, name="Lazer")
    second = create_category(client, name="Delivery")
    for category in (first, second):
        create_transaction(client, category["id"], amount_cents=15_000, date="2026-10-20")
        create_limit(client, category["id"])
    items = client.get("/api/alerts").json()["items"]
    assert len(items) == 2
    partial = client.post("/api/alerts/read", json={"ids": [items[0]["id"]]})
    assert (partial.status_code, partial.json()["unread"]) == (200, 1)
    everything = client.post("/api/alerts/read", json={})
    assert everything.json()["unread"] == 0
    assert all(item["read_at"] is not None for item in everything.json()["items"])


def test_suggestion_endpoint(client, monkeypatch):
    category = create_category(client)
    for day, cents in (("2026-07-10", 25_000), ("2026-08-10", 31_000), ("2026-09-10", 28_000)):
        create_transaction(client, category["id"], amount_cents=cents, date=day)
    monkeypatch.setattr(limits, "forecast_p50", lambda *args: {category["id"]: 30_412})
    response = client.get("/api/limits/suggestion", params={"category_id": category["id"]})
    assert response.json() == {
        "suggested_cents": 31_000,
        "low_cents": 25_000,
        "high_cents": 31_000,
        "months": 3,
    }
    missing = client.get("/api/limits/suggestion", params={"category_id": 999})
    assert missing.status_code == 404


def test_saving_the_same_amount_keeps_the_month_alerts(client):
    category = create_category(client)
    create_transaction(client, category["id"], amount_cents=27_000, date="2026-10-20")
    limit = create_limit(client, category["id"], amount_cents=30_000)
    before = client.post("/api/alerts/read", json={}).json()
    assert before["unread"] == 0
    assert client.put(f"/api/limits/{limit['id']}", json={"amount_cents": 30_000}).status_code == 200
    after = client.get("/api/alerts").json()
    assert after["unread"] == 0
    assert [item["id"] for item in after["items"]] == [item["id"] for item in before["items"]]
