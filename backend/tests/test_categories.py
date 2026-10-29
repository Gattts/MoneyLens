from datetime import date

from financeiro.domain.enums import Bucket, Kind, LineStatus, PaymentMethod
from financeiro.models import Category, InvoiceImport, InvoiceLine, Transaction
from tests.factories import create_card, create_category, create_income_category


def _use_category(db, category_id: int) -> None:
    db.add(
        Transaction(
            user_id=db.get(Category, category_id).user_id,
            description="Compra",
            kind=Kind.EXPENSE,
            amount_cents=1_000,
            date=date(2026, 10, 1),
            category_id=category_id,
            bucket=Bucket.NEEDS,
            payment_method=PaymentMethod.PIX,
        )
    )
    db.commit()


def test_create_and_list_categories(client):
    created = create_category(client, description="Itens do mercado")
    assert created["id"] > 0
    assert created["archived"] is False
    listed = client.get("/api/categories").json()
    assert [(c["name"], c["default_bucket"]) for c in listed] == [("Mercado", "needs")]


def test_expense_category_requires_a_budget_group(client):
    response = client.post("/api/categories", json={"name": "Lazer", "kind": "expense"})
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "default_bucket"


def test_income_category_cannot_have_a_budget_group(client):
    response = client.post(
        "/api/categories", json={"name": "Salário", "kind": "income", "default_bucket": "needs"}
    )
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "default_bucket"


def test_blank_name_gets_a_portuguese_message(client):
    response = client.post(
        "/api/categories", json={"name": "   ", "kind": "expense", "default_bucket": "needs"}
    )
    assert response.status_code == 422
    assert response.json() == {
        "detail": "Verifique os campos informados.",
        "code": "validation_error",
        "errors": [{"field": "name", "message": "Preencha este campo."}],
    }


def test_too_long_name_reports_the_limit(client):
    response = client.post(
        "/api/categories", json={"name": "x" * 61, "kind": "expense", "default_bucket": "needs"}
    )
    assert response.json()["errors"] == [{"field": "name", "message": "Use no máximo 60 caracteres."}]


def test_unknown_fields_are_rejected(client):
    response = client.post(
        "/api/categories",
        json={"name": "Lazer", "kind": "expense", "default_bucket": "wants", "id": 99},
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "id", "message": "Campo não permitido."}]


def test_invalid_option_and_malformed_json_get_portuguese_messages(client):
    bad_option = client.post("/api/categories", json={"name": "Lazer", "kind": "gasto"})
    assert {"field": "kind", "message": "Opção inválida."} in bad_option.json()["errors"]
    malformed = client.post(
        "/api/categories", content=b'{"name": ', headers={"content-type": "application/json"}
    )
    assert malformed.status_code == 422
    assert malformed.json()["errors"][0]["message"] == "O corpo da requisição não é um JSON válido."


def test_duplicate_name_is_rejected_ignoring_case_and_spaces(client):
    create_category(client, name="Mercado")
    response = client.post(
        "/api/categories", json={"name": " mercado ", "kind": "expense", "default_bucket": "needs"}
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Já existe uma categoria com esse nome."


def test_update_category(client):
    category = create_category(client)
    response = client.put(
        f"/api/categories/{category['id']}",
        json={"name": "Supermercado", "icon": "🧺", "kind": "expense", "default_bucket": "needs"},
    )
    assert response.status_code == 200
    assert (response.json()["name"], response.json()["icon"]) == ("Supermercado", "🧺")


def test_unknown_category_returns_404_in_portuguese(client):
    response = client.put(
        "/api/categories/999", json={"name": "X", "kind": "expense", "default_bucket": "needs"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Categoria não encontrada."


def test_category_in_use_cannot_be_deleted_but_can_be_archived(client, db):
    category = create_category(client)
    _use_category(db, category["id"])
    response = client.delete(f"/api/categories/{category['id']}")
    assert response.status_code == 409
    assert "arquive" in response.json()["detail"].lower()
    archived = client.put(
        f"/api/categories/{category['id']}",
        json={"name": "Mercado", "kind": "expense", "default_bucket": "needs", "archived": True},
    )
    assert archived.json()["archived"] is True


def test_kind_of_category_in_use_cannot_change(client, db):
    category = create_category(client)
    _use_category(db, category["id"])
    response = client.put(f"/api/categories/{category['id']}", json={"name": "Mercado", "kind": "income"})
    assert response.status_code == 409


def test_unused_category_can_be_deleted(client):
    category = create_category(client)
    other = create_income_category(client)
    assert client.delete(f"/api/categories/{category['id']}").status_code == 204
    assert [c["id"] for c in client.get("/api/categories").json()] == [other["id"]]


def test_category_used_by_invoice_line_cannot_be_deleted(client, db, user):
    card = create_card(client)
    category = create_category(client, name="Lazer", default_bucket="wants")
    invoice = InvoiceImport(
        user_id=user.id, card_id=card["id"], bank="inter", due_date=date(2026, 10, 12), total_cents=100
    )
    db.add(invoice)
    db.flush()
    db.add(
        InvoiceLine(
            import_id=invoice.id,
            position=1,
            date=date(2026, 9, 5),
            description="LOJA",
            merchant_key="LOJA",
            amount_cents=100,
            is_credit=False,
            status=LineStatus.IDENTIFIED,
            category_id=category["id"],
        )
    )
    db.commit()
    response = client.delete(f"/api/categories/{category['id']}")
    assert response.status_code == 409
    assert "linha(s) de fatura" in response.json()["detail"]
