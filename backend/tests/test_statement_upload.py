from tests.factories import create_income_category, create_recurring
from tests.invoice_samples import LOJA, UBER, invoice_pdf, upload
from tests.statement_samples import (
    APPLY,
    REDEEM,
    Day,
    Entry,
    pix_in,
    pix_out,
    statement_pages,
    statement_pdf,
    upload_statement,
)

DAYS = [
    Day(
        "02 OUT 2026",
        inflows=[pix_in("EMPRESA X", "1.500,00")],
        outflows=[pix_out("PADARIA", "12,50"), Entry(APPLY, "", "150,00")],
    ),
    Day("03 OUT 2026", inflows=[Entry(REDEEM, "", "27,00")]),
]


def _pdf(days: list[Day] = DAYS, **options) -> bytes:
    return statement_pdf(statement_pages(days, **options))


def _summary(body: dict) -> list[tuple]:
    return [
        (line["description"], line["kind"], line["payment_method"], line["status"], line["skip_reason"])
        for line in body["lines"]
    ]


def test_upload_statement_classifies_lines(client):
    response = upload_statement(client, _pdf())
    assert response.status_code == 201, response.text
    body = response.json()
    assert (body["source"], body["bank"], body["card_id"], body["due_date"]) == (
        "account_statement",
        "nubank",
        None,
        None,
    )
    assert (body["period_start"], body["period_end"]) == ("2026-10-01", "2026-10-27")
    assert body["total_cents"] == 1250 + 15000
    assert _summary(body) == [
        ("EMPRESA X", "income", "pix", "pending", None),
        ("PADARIA", "expense", "pix", "pending", None),
        ("Aplicação RDB", "expense", "transfer", "skipped", "investment"),
        ("Resgate RDB", "income", "transfer", "skipped", "investment"),
        ("Dinheiro guardado no período", "expense", "transfer", "pending", None),
    ]
    assert body["lines"][-1]["amount_cents"] == 15000 - 2700
    assert body["investment"] == {"applied_cents": 15000, "redeemed_cents": 2700}
    assert body["already_imported"] is False


def test_statement_sent_as_invoice_is_refused(client, card):
    response = upload(client, card["id"], _pdf())
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "file", "message": "Este arquivo é um extrato de conta. Escolha Extrato da conta."}
    ]


def test_invoice_sent_as_statement_is_refused(client):
    response = upload_statement(client, invoice_pdf(UBER, LOJA))
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {
            "field": "file",
            "message": "Este arquivo é uma fatura de cartão. Escolha Fatura do cartão e o cartão.",
        }
    ]


def test_invoice_requires_card(client):
    response = client.post(
        "/api/invoice-imports", files={"file": ("fatura.pdf", invoice_pdf(UBER, LOJA), "application/pdf")}
    )
    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "card_id", "message": "Escolha o cartão."}]


def test_mismatched_statement_saves_nothing(client):
    response = upload_statement(client, _pdf(income="1,00"))
    assert response.status_code == 422
    assert response.json()["errors"][0]["message"] == (
        "Não consegui conferir o extrato: os totais não batem. Nada foi importado."
    )
    assert client.get("/api/invoice-imports").json()["imports"] == []


def test_same_statement_twice_returns_200(client):
    first = upload_statement(client, _pdf()).json()
    again = upload_statement(client, _pdf())
    assert again.status_code == 200
    assert (again.json()["id"], again.json()["already_imported"]) == (first["id"], True)


def test_reimport_after_undo_is_fresh(client):
    first = upload_statement(client, _pdf()).json()
    assert client.delete(f"/api/invoice-imports/{first['id']}").status_code == 204
    again = upload_statement(client, _pdf())
    assert again.status_code == 201
    assert [line["skip_reason"] for line in again.json()["lines"]] == [
        None,
        None,
        "investment",
        "investment",
        None,
    ]


def test_list_mixes_invoices_and_statements_in_date_order(client, card, transport):
    october = upload(client, card["id"], invoice_pdf(UBER, LOJA, due="12/10/2026")).json()
    november = upload(client, card["id"], invoice_pdf(UBER, LOJA, due="12/11/2026")).json()
    statement = upload_statement(client, _pdf()).json()
    listed = client.get("/api/invoice-imports").json()["imports"]
    assert [item["id"] for item in listed] == [november["id"], statement["id"], october["id"]]
    assert [item["source"] for item in listed] == ["card_invoice", "account_statement", "card_invoice"]


def test_ignore_route_returns_the_detail(client):
    body = upload_statement(client, _pdf()).json()
    padaria = next(line for line in body["lines"] if line["description"] == "PADARIA")
    response = client.post(f"/api/invoice-lines/{padaria['id']}/ignore")
    assert response.status_code == 200
    updated = next(line for line in response.json()["lines"] if line["id"] == padaria["id"])
    assert (updated["status"], updated["skip_reason"]) == ("skipped", "ignored")
    assert client.post(f"/api/invoice-lines/{padaria['id']}/ignore").status_code == 409


def test_pending_recurring_is_named_on_the_duplicate(client):
    salary = create_income_category(client)
    create_recurring(
        client,
        salary["id"],
        description="Salário",
        kind="income",
        amount_cents=150000,
        day_of_month=2,
        payment_method="transfer",
    )
    body = upload_statement(client, _pdf()).json()
    empresa = body["lines"][0]
    assert (empresa["skip_reason"], empresa["duplicate_of"]) == ("duplicate", "Salário")
    assert body["lines"][1]["duplicate_of"] is None
