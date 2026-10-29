from datetime import date

from financeiro.domain.enums import LineStatus
from financeiro.models import InvoiceImport, InvoiceLine
from tests.factories import create_category, create_income_category, create_transaction
from tests.invoice_samples import LOJA, UBER, invoice_pdf, row, upload

PARCEL_1_OF_2 = row("10 de set. 2026", "UBER *VIAGEM (Parcela 01 de 02)", "R$ 40,00")


def _confirm(client, import_id: int):
    return client.post(f"/api/invoice-imports/{import_id}/confirm")


def _transactions(client, *months: str) -> list[dict]:
    return [tx for month in months for tx in client.get("/api/transactions", params={"month": month}).json()]


def _line(body: dict, description: str) -> dict:
    return next(line for line in body["lines"] if line["description"] == description)


def _resolve(client, line: dict, category_id: int, *, remember: bool):
    return client.put(
        f"/api/invoice-lines/{line['id']}", json={"category_id": category_id, "remember": remember}
    )


def test_confirm_creates_transactions_and_keeps_pending(client, card, transport):
    body = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    confirmed = _confirm(client, body["id"])
    assert confirmed.status_code == 200, confirmed.text
    detail = confirmed.json()
    assert detail["confirmed_at"] is not None
    assert (_line(detail, "UBER *TRIP")["status"], _line(detail, "LOJA NOVA")["status"]) == (
        "imported",
        "pending",
    )
    [tx] = _transactions(client, "2026-09")
    assert (tx["description"], tx["amount_cents"], tx["date"]) == ("UBER *TRIP", 2390, "2026-09-05")
    assert (tx["kind"], tx["payment_method"], tx["card_id"], tx["bucket"]) == (
        "expense",
        "credit_card",
        card["id"],
        "needs",
    )
    assert tx["notes"] == "Importado da fatura Inter (venc. 12/10/2026)"
    assert _line(detail, "UBER *TRIP")["transaction_id"] == tx["id"]

    again = _confirm(client, body["id"])
    assert again.status_code == 409
    assert again.json()["detail"] == "Esta fatura já foi confirmada."


def test_confirm_creates_future_installments(client, card, transport):
    parcel = row("31 de jan. 2026", "UBER *VIAGEM (Parcela 01 de 03)", "R$ 30,00")
    body = upload(client, card["id"], invoice_pdf(parcel, total="R$ 30,00", due="12/02/2026")).json()
    _confirm(client, body["id"])
    parcels = _transactions(client, "2026-01", "2026-02", "2026-03")
    assert [(tx["date"], tx["installment_number"], tx["installment_total"]) for tx in parcels] == [
        ("2026-01-31", 1, 3),
        ("2026-02-28", 2, 3),
        ("2026-03-31", 3, 3),
    ]
    assert len({tx["installment_group"] for tx in parcels}) == 1
    assert {tx["amount_cents"] for tx in parcels} == {3000}


def test_series_seen_from_the_middle_creates_only_the_remaining_parcels(client, card, transport):
    parcel = row("10 de jul. 2026", "UBER *VIAGEM (Parcela 03 de 04)", "R$ 25,00")
    body = upload(client, card["id"], invoice_pdf(parcel, total="R$ 25,00")).json()
    _confirm(client, body["id"])
    parcels = _transactions(client, "2026-07", "2026-08", "2026-09", "2026-10")
    assert [(tx["date"], tx["installment_number"]) for tx in parcels] == [
        ("2026-09-10", 3),
        ("2026-10-10", 4),
    ]


def test_resolve_with_remember_learns_and_applies_to_other_pending(client, card, transport):
    leisure = create_category(client, name="Lazer", default_bucket="wants")
    first = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    second = upload(client, card["id"], invoice_pdf(UBER, LOJA, due="12/11/2026")).json()

    response = _resolve(client, _line(first, "LOJA NOVA"), leisure["id"], remember=True)
    assert response.status_code == 200, response.text
    assert response.json()["id"] == first["id"]
    assert _line(response.json(), "LOJA NOVA")["status"] == "identified"
    other = client.get(f"/api/invoice-imports/{second['id']}").json()
    assert (_line(other, "LOJA NOVA")["status"], _line(other, "LOJA NOVA")["category_id"]) == (
        "identified",
        leisure["id"],
    )
    rules = client.get("/api/category-rules").json()
    assert {(r["pattern"], r["match_type"], r["source"], r["category_id"]) for r in rules} >= {
        ("LOJA NOVA", "exact", "learned", leisure["id"])
    }
    third = upload(client, card["id"], invoice_pdf(UBER, LOJA, due="12/12/2026")).json()
    assert _line(third, "LOJA NOVA")["status"] == "identified"


def test_resolve_without_remember_creates_no_rule(client, card, transport):
    leisure = create_category(client, name="Lazer", default_bucket="wants")
    first = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    second = upload(client, card["id"], invoice_pdf(UBER, LOJA, due="12/11/2026")).json()
    assert _resolve(client, _line(first, "LOJA NOVA"), leisure["id"], remember=False).status_code == 200
    assert [r["pattern"] for r in client.get("/api/category-rules").json()] == ["UBER"]
    other = client.get(f"/api/invoice-imports/{second['id']}").json()
    assert _line(other, "LOJA NOVA")["status"] == "pending"


def test_resolve_after_confirm_posts_immediately(client, card, transport):
    leisure = create_category(client, name="Lazer", default_bucket="wants")
    body = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    _confirm(client, body["id"])
    detail = _resolve(client, _line(body, "LOJA NOVA"), leisure["id"], remember=False).json()
    assert _line(detail, "LOJA NOVA")["status"] == "imported"
    assert _line(detail, "LOJA NOVA")["transaction_id"] is not None
    assert len(_transactions(client, "2026-09")) == 2


def test_resolve_imported_line_conflicts(client, card, transport):
    body = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    _confirm(client, body["id"])
    response = _resolve(client, _line(body, "UBER *TRIP"), transport["id"], remember=False)
    assert response.status_code == 409
    assert response.json()["detail"] == "Esta linha já foi importada ou está fora da importação."
    assert len(_transactions(client, "2026-09")) == 1


def test_resolve_rejects_income_or_archived_category(client, card, transport):
    body = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    income = create_income_category(client)
    archived = create_category(client, name="Velha", default_bucket="wants", archived=True)
    for category in (income, archived):
        response = _resolve(client, _line(body, "LOJA NOVA"), category["id"], remember=True)
        assert response.status_code == 422
        assert response.json()["errors"][0]["field"] == "category_id"
    assert client.get("/api/category-rules").json()[0]["pattern"] == "UBER"


def test_include_duplicate(client, card, transport):
    create_transaction(
        client,
        transport["id"],
        amount_cents=2390,
        date="2026-09-04",
        payment_method="credit_card",
        card_id=card["id"],
    )
    body = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    assert _line(body, "UBER *TRIP")["skip_reason"] == "duplicate"
    included = client.post(f"/api/invoice-lines/{_line(body, 'UBER *TRIP')['id']}/include").json()
    assert (_line(included, "UBER *TRIP")["status"], _line(included, "UBER *TRIP")["skip_reason"]) == (
        "identified",
        None,
    )
    refused = client.post(f"/api/invoice-lines/{_line(body, 'LOJA NOVA')['id']}/include")
    assert refused.status_code == 409


def test_undo_deletes_created_transactions_and_installments(client, card, transport):
    manual = create_transaction(
        client,
        transport["id"],
        amount_cents=999,
        date="2026-09-20",
        payment_method="credit_card",
        card_id=card["id"],
    )
    body = upload(client, card["id"], invoice_pdf(UBER, PARCEL_1_OF_2, total="R$ 63,90")).json()
    _confirm(client, body["id"])
    assert len(_transactions(client, "2026-09", "2026-10")) == 4  # manual + UBER + 2 parcelas
    assert client.delete(f"/api/invoice-imports/{body['id']}").status_code == 204
    assert [tx["id"] for tx in _transactions(client, "2026-09", "2026-10")] == [manual["id"]]
    assert client.get(f"/api/invoice-imports/{body['id']}").status_code == 404


def test_discard_unconfirmed_import(client, card, transport):
    body = upload(client, card["id"], invoice_pdf(UBER, LOJA)).json()
    assert client.delete(f"/api/invoice-imports/{body['id']}").status_code == 204
    assert _transactions(client, "2026-09") == []
    assert client.get(f"/api/invoice-imports/{body['id']}").status_code == 404
    assert upload(client, card["id"], invoice_pdf(UBER, LOJA)).status_code == 201


def test_long_description_is_truncated_on_posting(client, db, user, card, transport):
    invoice = InvoiceImport(
        user_id=user.id, card_id=card["id"], bank="inter", due_date=date(2026, 10, 12), total_cents=100
    )
    db.add(invoice)
    db.flush()
    description = "LOJA " + "X" * 145
    db.add(
        InvoiceLine(
            import_id=invoice.id,
            position=1,
            date=date(2026, 9, 5),
            description=description,
            merchant_key=description,
            amount_cents=100,
            is_credit=False,
            status=LineStatus.IDENTIFIED,
            category_id=transport["id"],
        )
    )
    db.commit()
    assert _confirm(client, invoice.id).status_code == 200
    [tx] = _transactions(client, "2026-09")
    assert tx["description"] == description[:120]


def test_actions_on_missing_items_are_404(client):
    assert _confirm(client, 999).status_code == 404
    assert client.delete("/api/invoice-imports/999").status_code == 404
    assert client.put("/api/invoice-lines/999", json={"category_id": 1, "remember": True}).status_code == 404
    assert client.post("/api/invoice-lines/999/include").status_code == 404


def _parcels(client) -> list[tuple[int, str, int]]:
    months = ("2026-01", "2026-02", "2026-03", "2026-04", "2026-05")
    found = [tx for tx in _transactions(client, *months) if tx["installment_total"] == 3]
    return sorted((tx["installment_number"], tx["date"], tx["amount_cents"]) for tx in found)


def _series_invoice(client, card, number: int, due: str) -> dict:
    parcel = row("10 de jan. 2026", f"UBER *VIAGEM (Parcela 0{number} de 03)", "R$ 30,00")
    return upload(client, card["id"], invoice_pdf(parcel, total="R$ 30,00", due=due)).json()


EXPECTED_SERIES = [(1, "2026-01-10", 3000), (2, "2026-02-10", 3000), (3, "2026-03-10", 3000)]


def test_out_of_order_imports_do_not_duplicate_installments(client, card, transport):
    march = _series_invoice(client, card, 2, "12/03/2026")
    _confirm(client, march["id"])
    february = _series_invoice(client, card, 1, "12/02/2026")
    _confirm(client, february["id"])
    assert _parcels(client) == EXPECTED_SERIES


def test_two_open_invoices_of_the_same_series_do_not_duplicate(client, card, transport):
    february = _series_invoice(client, card, 1, "12/02/2026")
    march = _series_invoice(client, card, 2, "12/03/2026")
    _confirm(client, february["id"])
    confirmed_march = _confirm(client, march["id"]).json()
    assert _parcels(client) == EXPECTED_SERIES
    assert confirmed_march["lines"][0]["skip_reason"] == "existing_installment"


def test_undo_keeps_parcels_another_invoice_relies_on(client, card, transport):
    february = _series_invoice(client, card, 1, "12/02/2026")
    _confirm(client, february["id"])
    march = _series_invoice(client, card, 2, "12/03/2026")
    assert march["lines"][0]["skip_reason"] == "existing_installment"
    assert client.delete(f"/api/invoice-imports/{february['id']}").status_code == 204
    assert [number for number, _, _ in _parcels(client)] == [2]
