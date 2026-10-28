import logging

import pytest

from financeiro.models import CreditCard
from financeiro.services.invoices import importer
from tests.factories import create_card, create_category, create_transaction, create_transactions
from tests.invoice_samples import inter_pdf, inter_text, row

UBER = row("05 de set. 2026", "UBER *TRIP", "R$ 23,90")
LOJA = row("06 de set. 2026", "LOJA NOVA", "R$ 50,00")
PAYMENT = row("07 de set. 2026", "PAGAMENTO ON LINE", "R$ 100,00", credit=True)


def _pdf(*rows: str, total: str = "R$ 73,90", due: str = "12/10/2026", password: str | None = None) -> bytes:
    return inter_pdf(inter_text([("1111****2222", list(rows), total)], due=due), password=password)


def _upload(client, card_id: int, pdf: bytes, **form: str):
    return client.post(
        "/api/invoice-imports",
        data={"card_id": str(card_id), **form},
        files={"file": ("fatura.pdf", pdf, "application/pdf")},
    )


@pytest.fixture
def card(client) -> dict:
    return create_card(client, name="Inter")


@pytest.fixture
def transport(client) -> dict:
    category = create_category(client, name="Transporte", default_bucket="needs")
    rule = {"pattern": "UBER", "match_type": "contains", "category_id": category["id"]}
    assert client.post("/api/category-rules", json=rule).status_code == 201
    return category


def test_upload_classifies_lines(client, card, transport):
    response = _upload(client, card["id"], _pdf(UBER, LOJA, PAYMENT))
    assert response.status_code == 201, response.text
    body = response.json()
    statuses = {line["description"]: (line["status"], line["skip_reason"]) for line in body["lines"]}
    assert statuses == {
        "UBER *TRIP": ("identified", None),
        "LOJA NOVA": ("pending", None),
        "PAGAMENTO ON LINE": ("skipped", "payment"),
    }
    assert (body["pending_count"], body["pending_cents"], body["total_cents"], body["line_count"]) == (
        1,
        5000,
        7390,
        3,
    )
    assert body["lines"][0]["category_id"] == transport["id"]
    assert body["already_imported"] is False


def test_password_flow_and_saving(client, db, card, transport):
    locked = _pdf(UBER, LOJA, password="4321")
    missing = _upload(client, card["id"], locked)
    assert missing.status_code == 422
    assert missing.json()["errors"] == [{"field": "password", "message": "Esta fatura tem senha."}]
    assert _upload(client, card["id"], locked, password="errada").json()["errors"][0]["message"] == (
        "Senha incorreta."
    )
    assert _upload(client, card["id"], locked, password="4321", save_password="true").status_code == 201
    assert client.get("/api/cards").json()[0]["has_invoice_password"] is True
    stored = db.get(CreditCard, card["id"])
    db.refresh(stored)
    assert stored.invoice_password_encrypted is not None
    assert "4321" not in stored.invoice_password_encrypted


def test_password_is_not_saved_by_default(client, card, transport):
    assert _upload(client, card["id"], _pdf(UBER, LOJA, password="4321"), password="4321").status_code == 201
    assert client.get("/api/cards").json()[0]["has_invoice_password"] is False


def test_saved_password_is_used_on_next_upload(client, card, transport):
    first = _upload(
        client, card["id"], _pdf(UBER, LOJA, password="4321"), password="4321", save_password="true"
    )
    assert first.status_code == 201
    next_month = _pdf(UBER, LOJA, due="12/11/2026", password="4321")
    assert _upload(client, card["id"], next_month).status_code == 201


def test_same_invoice_returns_existing(client, card, transport):
    first = _upload(client, card["id"], _pdf(UBER, LOJA)).json()
    second = _upload(client, card["id"], _pdf(UBER, LOJA))
    assert second.status_code == 200
    assert (second.json()["id"], second.json()["already_imported"]) == (first["id"], True)


def test_same_invoice_on_another_card_is_a_new_import(client, card, transport):
    other = create_card(client, name="Outro")
    _upload(client, card["id"], _pdf(UBER, LOJA))
    assert _upload(client, other["id"], _pdf(UBER, LOJA)).status_code == 201


def test_upload_race_returns_existing_import(client, card, transport, monkeypatch):
    first = _upload(client, card["id"], _pdf(UBER, LOJA)).json()
    real, calls = importer.find_import, []

    def lookup_misses_once(session, card_id, due_date):
        # Simula só a janela da corrida: o outro envio ainda não tinha gravado quando este conferiu.
        calls.append(card_id)
        return None if len(calls) == 1 else real(session, card_id, due_date)

    monkeypatch.setattr(importer, "find_import", lookup_misses_once)
    second = _upload(client, card["id"], _pdf(UBER, LOJA))
    assert second.status_code == 200
    assert second.json()["id"] == first["id"]


def _installment_purchase(client, card, category) -> list[dict]:
    return create_transactions(
        client,
        category["id"],
        description="GAMES *LOJA",
        amount_cents=7869,
        date="2026-09-03",
        payment_method="credit_card",
        card_id=card["id"],
        installments=2,
    )


@pytest.mark.parametrize("line_date", ["03 de set. 2026", "03 de out. 2026"])
def test_existing_installment_is_skipped_and_cent_fixed(client, card, transport, line_date):
    parcels = _installment_purchase(client, card, transport)
    assert [parcel["amount_cents"] for parcel in parcels] == [3935, 3934]
    text_row = row(line_date, "GAMES *LOJA (Parcela 02 de 02)", "R$ 39,35")
    body = _upload(client, card["id"], _pdf(text_row, total="R$ 39,35")).json()
    assert (body["lines"][0]["status"], body["lines"][0]["skip_reason"]) == (
        "skipped",
        "existing_installment",
    )
    october = client.get("/api/transactions", params={"month": "2026-10"}).json()
    assert [t["amount_cents"] for t in october if t["installment_number"] == 2] == [3935]


def test_possible_duplicate_is_skipped(client, card, transport):
    create_transaction(
        client,
        transport["id"],
        description="Uber que lancei na mão",
        amount_cents=2390,
        date="2026-09-04",
        payment_method="credit_card",
        card_id=card["id"],
    )
    body = _upload(client, card["id"], _pdf(UBER, LOJA)).json()
    assert (body["lines"][0]["status"], body["lines"][0]["skip_reason"]) == ("skipped", "duplicate")


def test_rule_of_archived_category_is_ignored(client, card, transport):
    fields = {key: transport[key] for key in ("name", "icon", "description", "kind", "default_bucket")}
    assert (
        client.put(f"/api/categories/{transport['id']}", json=fields | {"archived": True}).status_code == 200
    )
    body = _upload(client, card["id"], _pdf(UBER, LOJA)).json()
    assert body["lines"][0]["status"] == "pending"


def test_archived_card_is_refused(client, transport):
    archived = create_card(client, name="Velho", archived=True)
    response = _upload(client, archived["id"], _pdf(UBER, LOJA))
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "card_id", "message": "Este cartão está arquivado. Escolha outro ou desarquive-o."}
    ]


def test_unknown_card_is_refused(client, transport):
    response = _upload(client, 999, _pdf(UBER, LOJA))
    assert response.json()["errors"] == [{"field": "card_id", "message": "Cartão não encontrado."}]


def test_not_a_pdf_is_refused(client, card):
    response = _upload(client, card["id"], b"nada")
    assert response.json()["errors"] == [{"field": "file", "message": "O arquivo não é um PDF válido."}]


def test_list_and_detail_report_standby(client, card, transport):
    created = _upload(client, card["id"], _pdf(UBER, LOJA)).json()
    listed = client.get("/api/invoice-imports").json()
    assert (listed["standby_count"], listed["standby_cents"]) == (1, 5000)
    assert [(item["id"], item["pending_count"]) for item in listed["imports"]] == [(created["id"], 1)]
    detail = client.get(f"/api/invoice-imports/{created['id']}").json()
    assert [line["position"] for line in detail["lines"]] == [1, 2]
    assert client.get("/api/invoice-imports/999").status_code == 404


def test_upload_logs_only_counts(client, card, transport, caplog):
    caplog.set_level(logging.INFO)
    _upload(client, card["id"], _pdf(UBER, LOJA))
    assert "Fatura lida" in caplog.text
    for secret in ("UBER", "LOJA NOVA", "2390", "23,90"):
        assert secret not in caplog.text
