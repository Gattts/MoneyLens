from datetime import date

from financeiro.models import CreditCard, InvoiceImport
from financeiro.services.secret_box import seal
from tests.factories import create_card, create_category, create_transaction

CARD = {"name": "Nubank", "limit_cents": 300_000, "closing_day": 10, "due_day": 17}


def test_limit_usage_counts_open_invoice_and_future_installments(client, card_with_purchases):
    listed = client.get("/api/cards").json()[0]
    assert (listed["used_cents"], listed["available_cents"]) == (50_000, 250_000)
    assert listed["current_invoice"] == {
        "month": "2026-11",
        "closing_date": "2026-11-10",
        "due_date": "2026-11-17",
        "total_cents": 30_000,
        "status": "open",
        "paid_cents": 0,
        "remaining_cents": 30_000,
        "paid_on": None,
    }


def test_invoice_uses_the_billing_cycle(client, card_with_purchases):
    response = client.get(f"/api/cards/{card_with_purchases['id']}/invoice", params={"month": "2026-11"})
    invoice = response.json()
    assert (invoice["period_start"], invoice["period_end"]) == ("2026-10-10", "2026-11-09")
    assert (invoice["status"], invoice["total_cents"]) == ("open", 30_000)
    assert [t["date"] for t in invoice["transactions"]] == ["2026-10-15", "2026-10-20"]


def test_past_invoice_and_default_month(client, card_with_purchases):
    url = f"/api/cards/{card_with_purchases['id']}/invoice"
    october = client.get(url, params={"month": "2026-10"}).json()
    assert (october["status"], october["total_cents"]) == ("paid_before_tracking", 10_000)
    assert client.get(url).json()["month"] == "2026-11"
    assert client.get("/api/cards/999/invoice").status_code == 404


def test_create_and_list_cards(client):
    created = create_card(client)
    assert (created["name"], created["closing_day"], created["due_day"]) == ("Nubank", 10, 17)
    assert [card["id"] for card in client.get("/api/cards").json()] == [created["id"]]


def test_days_outside_the_month_are_rejected(client):
    response = client.post("/api/cards", json=CARD | {"closing_day": 0, "due_day": 32})
    errors = {error["field"]: error["message"] for error in response.json()["errors"]}
    assert errors == {"closing_day": "Informe um valor a partir de 1.", "due_day": "Informe um valor até 31."}


def test_negative_limit_is_rejected(client):
    response = client.post("/api/cards", json=CARD | {"limit_cents": -1})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "limit_cents"


def test_duplicate_card_name_is_rejected(client):
    create_card(client)
    response = client.post("/api/cards", json=CARD | {"name": "NUBANK"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe um cartão com esse nome."


def test_update_card_and_unknown_card(client):
    card = create_card(client)
    updated = client.put(f"/api/cards/{card['id']}", json=CARD | {"limit_cents": 500_000})
    assert updated.json()["limit_cents"] == 500_000
    missing = client.put("/api/cards/999", json=CARD)
    assert (missing.status_code, missing.json()["detail"]) == (404, "Cartão não encontrado.")


def test_card_in_use_must_be_archived_instead_of_deleted(client):
    card = create_card(client)
    category = create_category(client)
    create_transaction(client, category["id"], payment_method="credit_card", card_id=card["id"])
    response = client.delete(f"/api/cards/{card['id']}")
    assert response.status_code == 409
    assert "arquive" in response.json()["detail"].lower()


def test_unused_card_can_be_deleted(client):
    card = create_card(client)
    assert client.delete(f"/api/cards/{card['id']}").status_code == 204
    assert client.get("/api/cards").json() == []


def test_card_with_invoice_import_cannot_be_deleted(client, db, user):
    card = create_card(client)
    db.add(
        InvoiceImport(
            user_id=user.id, card_id=card["id"], bank="inter", due_date=date(2026, 10, 12), total_cents=100
        )
    )
    db.commit()
    response = client.delete(f"/api/cards/{card['id']}")
    assert response.status_code == 409
    assert "fatura" in response.json()["detail"]


def test_card_reports_saved_password_and_forgets_it(client, db):
    card = create_card(client)
    db.get(CreditCard, card["id"]).invoice_password_encrypted = seal("senha-de-teste", "k" * 40)
    db.commit()
    listed = client.get("/api/cards").json()[0]
    assert listed["has_invoice_password"] is True
    assert "invoice_password_encrypted" not in listed

    assert client.delete(f"/api/cards/{card['id']}/invoice-password").status_code == 204
    assert client.get("/api/cards").json()[0]["has_invoice_password"] is False
