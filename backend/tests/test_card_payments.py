from datetime import date

from sqlalchemy import select

from financeiro.domain.enums import PaymentMethod, PaymentSource
from financeiro.domain.statements import ParsedStatement, ParsedStatementLine, StatementNature
from financeiro.models import CardPayment, CreditCard
from financeiro.services.invoices.statement_importer import import_statement
from tests.factories import create_card, create_category, create_transaction
from tests.invoice_samples import LOJA, PAYMENT, UBER, invoice_pdf, upload

TRACKED = date(2026, 9, 1)


def _track_from(db, card_id: int, since: date = TRACKED) -> None:
    card = db.get(CreditCard, card_id)
    card.payments_since = since
    db.commit()


def _pay(db, card_id: int, month: date, cents: int, paid_on: date) -> CardPayment:
    card = db.get(CreditCard, card_id)
    payment = CardPayment(
        user_id=card.user_id,
        card_id=card_id,
        invoice_month=month,
        paid_on=paid_on,
        amount_cents=cents,
        source=PaymentSource.MANUAL,
    )
    db.add(payment)
    db.commit()
    return payment


def _card(client, card_id: int) -> dict:
    return next(card for card in client.get("/api/cards").json() if card["id"] == card_id)


def _invoice(client, card_id: int, month: str) -> dict:
    return client.get(f"/api/cards/{card_id}/invoice", params={"month": month}).json()


def test_overdue_invoice_keeps_using_the_limit(client, db, card_with_purchases):
    """Hoje 27/10: a fatura de outubro (R$ 100) venceu em 17/10 sem pagamento registrado."""
    _track_from(db, card_with_purchases["id"])
    assert _card(client, card_with_purchases["id"])["used_cents"] == 60_000
    october = _invoice(client, card_with_purchases["id"], "2026-10")
    assert (october["status"], october["paid_cents"], october["remaining_cents"]) == ("overdue", 0, 10_000)


def test_payment_before_due_frees_the_limit(client, db):
    """Fecha dia 20 e vence dia 30: em 27/10 a fatura de outubro fechou e ainda não venceu."""
    card = create_card(client, closing_day=20, due_day=30)
    category = create_category(client)
    create_transaction(
        client,
        category["id"],
        amount_cents=10_000,
        date="2026-10-05",
        payment_method="credit_card",
        card_id=card["id"],
    )
    _track_from(db, card["id"])
    assert (_card(client, card["id"])["used_cents"], _invoice(client, card["id"], "2026-10")["status"]) == (
        10_000,
        "closed",
    )
    _pay(db, card["id"], date(2026, 10, 1), 10_000, date(2026, 10, 25))
    october = _invoice(client, card["id"], "2026-10")
    assert (october["status"], october["paid_on"], october["remaining_cents"]) == ("paid", "2026-10-25", 0)
    assert _card(client, card["id"])["used_cents"] == 0


def test_partial_payment_shows_remaining(client, db, card_with_purchases):
    _track_from(db, card_with_purchases["id"])
    _pay(db, card_with_purchases["id"], date(2026, 10, 1), 4_000, date(2026, 10, 16))
    october = _invoice(client, card_with_purchases["id"], "2026-10")
    assert (october["status"], october["paid_cents"], october["remaining_cents"]) == (
        "partially_paid",
        4_000,
        6_000,
    )
    assert _card(client, card_with_purchases["id"])["used_cents"] == 56_000


def test_invoice_lists_its_payments(client, db, card_with_purchases):
    _track_from(db, card_with_purchases["id"])
    first = _pay(db, card_with_purchases["id"], date(2026, 10, 1), 4_000, date(2026, 10, 16))
    second = _pay(db, card_with_purchases["id"], date(2026, 10, 1), 6_000, date(2026, 10, 20))
    october = _invoice(client, card_with_purchases["id"], "2026-10")
    assert october["payments"] == [
        {"id": first.id, "paid_on": "2026-10-16", "amount_cents": 4_000, "source": "manual"},
        {"id": second.id, "paid_on": "2026-10-20", "amount_cents": 6_000, "source": "manual"},
    ]
    assert (october["status"], october["paid_on"]) == ("paid", "2026-10-20")


def test_new_card_tracks_payments_from_today(client, db):
    card = create_card(client)
    assert db.scalar(select(CreditCard.payments_since).where(CreditCard.id == card["id"])) == date(
        2026, 10, 27
    )


def _pay_by_api(client, card_id: int, **overrides):
    body = {"invoice_month": "2026-10", "paid_on": "2026-10-16", "amount_cents": 10_000} | overrides
    return client.post(f"/api/cards/{card_id}/payments", json=body)


def test_manual_payment_marks_the_invoice_and_can_be_deleted(client, db, card_with_purchases):
    _track_from(db, card_with_purchases["id"])
    response = _pay_by_api(client, card_with_purchases["id"])
    assert response.status_code == 201, response.text
    october = response.json()
    assert (october["month"], october["status"], october["paid_on"]) == ("2026-10", "paid", "2026-10-16")
    [payment] = october["payments"]
    assert payment["source"] == "manual"
    assert client.delete(f"/api/card-payments/{payment['id']}").status_code == 204
    assert _invoice(client, card_with_purchases["id"], "2026-10")["status"] == "overdue"


def test_open_invoice_cannot_be_paid(client, card_with_purchases):
    response = _pay_by_api(client, card_with_purchases["id"], invoice_month="2026-11")
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "invoice_month", "message": "Esta fatura ainda não fechou."}
    ]


def test_payment_date_before_the_invoice_period_is_refused(client, card_with_purchases):
    response = _pay_by_api(client, card_with_purchases["id"], paid_on="2026-09-09")
    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "paid_on", "message": "A data é anterior ao período desta fatura."}
    ]


def test_zero_amount_is_refused(client, card_with_purchases):
    response = _pay_by_api(client, card_with_purchases["id"], amount_cents=0)
    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "amount_cents"


def test_archived_card_still_records_payments(client, card_with_purchases):
    archived = {"name": "Nubank", "limit_cents": 300_000, "closing_day": 10, "due_day": 17, "archived": True}
    assert client.put(f"/api/cards/{card_with_purchases['id']}", json=archived).status_code == 200
    assert _pay_by_api(client, card_with_purchases["id"]).status_code == 201


def test_card_with_payment_cannot_be_deleted(client):
    card = create_card(client, name="Sem compras")
    assert _pay_by_api(client, card["id"], amount_cents=100).status_code == 201
    response = client.delete(f"/api/cards/{card['id']}")
    assert response.status_code == 409


def _upload_with_payment(client, card_id: int) -> dict:
    """A fatura traz o crédito "PAGAMENTO ON LINE" (R$ 100,00 em 07/09), que paga a fatura de agosto."""
    response = upload(client, card_id, invoice_pdf(UBER, LOJA, PAYMENT))
    assert response.status_code == 201, response.text
    return response.json()


def test_next_invoice_registers_the_payment_of_the_previous_one(client, db, card, transport):
    _track_from(db, card["id"], date(2026, 8, 1))
    body = _upload_with_payment(client, card["id"])
    august = _invoice(client, card["id"], "2026-08")
    [payment] = august["payments"]
    assert (payment["paid_on"], payment["amount_cents"], payment["source"]) == (
        "2026-09-07",
        10_000,
        "card_invoice",
    )
    line = next(line for line in body["lines"] if line["skip_reason"] == "payment")
    assert line["payment_id"] == payment["id"]
    assert all(other["payment_id"] is None for other in body["lines"] if other is not line)


def test_payment_from_an_invoice_is_removed_only_by_undoing_the_import(client, db, card, transport):
    _track_from(db, card["id"], date(2026, 8, 1))
    body = _upload_with_payment(client, card["id"])
    [payment] = _invoice(client, card["id"], "2026-08")["payments"]
    refused = client.delete(f"/api/card-payments/{payment['id']}")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "Desfaça a importação da fatura para tirar este pagamento."
    assert client.delete(f"/api/invoice-imports/{body['id']}").status_code == 204
    assert _invoice(client, card["id"], "2026-08")["payments"] == []


def test_payment_of_an_invoice_before_the_mark_changes_nothing(client, card, transport):
    """O cartão acompanha pagamentos desde hoje (27/10): a fatura de agosto venceu antes do marco."""
    used_before = _card(client, card["id"])["used_cents"]
    _upload_with_payment(client, card["id"])
    august = _invoice(client, card["id"], "2026-08")
    assert (august["status"], len(august["payments"])) == ("paid_before_tracking", 1)
    assert _card(client, card["id"])["used_cents"] == used_before


def _closed_invoice_card(client, db, name: str = "Inter", cents: int = 12_345) -> dict:
    """Fecha dia 20 e vence dia 30: em 27/10 a fatura de outubro já fechou e ainda não venceu."""
    card = create_card(client, name=name, closing_day=20, due_day=30)
    category = create_category(client, name=f"Compras {name}")
    create_transaction(
        client,
        category["id"],
        amount_cents=cents,
        date="2026-10-05",
        payment_method="credit_card",
        card_id=card["id"],
    )
    _track_from(db, card["id"])
    return card


def _statement_with(db, user, *lines: ParsedStatementLine) -> int:
    parsed = ParsedStatement("nubank", "ANA SOUZA", date(2026, 10, 1), date(2026, 10, 27), list(lines))
    statement, _ = import_statement(db, user.id, parsed)
    return statement.id


def _pix(description: str, cents: int, day: int = 26, nature: StatementNature = StatementNature.OUTFLOW):
    method = PaymentMethod.TRANSFER if nature is StatementNature.CARD_PAYMENT else PaymentMethod.PIX
    return ParsedStatementLine(1, date(2026, 10, day), nature, False, description, description, cents, method)


def _first_line(client, statement_id: int) -> dict:
    return client.get(f"/api/invoice-imports/{statement_id}").json()["lines"][0]


def test_pix_matching_an_invoice_becomes_a_payment_suggestion(client, db, user):
    card = _closed_invoice_card(client, db)
    line = _first_line(client, _statement_with(db, user, _pix("BANCO INTER", 12_345)))
    assert (line["status"], line["skip_reason"]) == ("skipped", "card_payment")
    assert line["payment_suggestion"] == {
        "card_id": card["id"],
        "card_name": "Inter",
        "invoice_month": "2026-10",
        "due_date": "2026-10-30",
    }


def test_pix_of_another_amount_is_not_a_suggestion(client, db, user):
    _closed_invoice_card(client, db)
    line = _first_line(client, _statement_with(db, user, _pix("BANCO INTER", 12_344)))
    assert (line["status"], line["payment_suggestion"]) == ("pending", None)


def test_card_payment_line_without_a_matching_invoice_has_no_suggestion(client, db, user):
    _closed_invoice_card(client, db)
    statement = _statement_with(
        db, user, _pix("Pagamento de fatura", 99_900, nature=StatementNature.CARD_PAYMENT)
    )
    line = _first_line(client, statement)
    assert (line["skip_reason"], line["payment_suggestion"]) == ("card_payment", None)


def test_two_matching_invoices_give_no_single_suggestion(client, db, user):
    _closed_invoice_card(client, db, "Inter")
    _closed_invoice_card(client, db, "Outro")
    line = _first_line(client, _statement_with(db, user, _pix("BANCO", 12_345)))
    assert (line["skip_reason"], line["payment_suggestion"]) == ("card_payment", None)


def _register(client, line_id: int, card_id: int, month: str = "2026-10"):
    return client.post(
        f"/api/invoice-lines/{line_id}/card-payment", json={"card_id": card_id, "invoice_month": month}
    )


def test_register_payment_from_the_statement(client, db, user):
    card = _closed_invoice_card(client, db)
    statement = _statement_with(db, user, _pix("BANCO INTER", 12_345))
    line = _first_line(client, statement)
    response = _register(client, line["id"], card["id"])
    assert response.status_code == 200, response.text
    registered = response.json()["lines"][0]
    assert (registered["payment_suggestion"], registered["skip_reason"]) == (None, "card_payment")
    october = _invoice(client, card["id"], "2026-10")
    assert (october["status"], october["payments"][0]["source"]) == ("paid", "account_statement")
    assert registered["payment_id"] == october["payments"][0]["id"]
    again = _register(client, line["id"], card["id"])
    assert again.status_code == 409
    assert again.json()["detail"] == "Este pagamento já foi registrado. Exclua o pagamento antes."
    assert len(_invoice(client, card["id"], "2026-10")["payments"]) == 1


def test_not_a_payment_returns_the_line_to_the_normal_flow(client, db, user):
    _closed_invoice_card(client, db)
    line = _first_line(client, _statement_with(db, user, _pix("BANCO INTER", 12_345)))
    included = client.post(f"/api/invoice-lines/{line['id']}/include")
    assert included.status_code == 200
    assert (included.json()["lines"][0]["status"], included.json()["lines"][0]["skip_reason"]) == (
        "pending",
        None,
    )


def test_registered_payment_line_cannot_be_included(client, db, user):
    card = _closed_invoice_card(client, db)
    line = _first_line(client, _statement_with(db, user, _pix("BANCO INTER", 12_345)))
    _register(client, line["id"], card["id"])
    refused = client.post(f"/api/invoice-lines/{line['id']}/include")
    assert refused.status_code == 409
    assert refused.json()["detail"] == "Este pagamento já foi registrado. Exclua o pagamento antes."


def test_deleting_a_statement_payment_brings_the_suggestion_back(client, db, user):
    card = _closed_invoice_card(client, db)
    statement = _statement_with(db, user, _pix("BANCO INTER", 12_345))
    line = _first_line(client, statement)
    payment_id = _register(client, line["id"], card["id"]).json()["lines"][0]["payment_id"]
    assert client.delete(f"/api/card-payments/{payment_id}").status_code == 204
    again = _first_line(client, statement)
    assert (again["payment_id"], again["payment_suggestion"]["card_id"]) == (None, card["id"])


def test_line_payment_needs_an_owned_card(client, other_client, db, user, second_user):
    _closed_invoice_card(client, db)
    line = _first_line(client, _statement_with(db, user, _pix("BANCO INTER", 12_345)))
    theirs = create_card(other_client, name="Deles")
    refused = _register(client, line["id"], theirs["id"])
    assert refused.status_code == 422
    assert refused.json()["errors"] == [{"field": "card_id", "message": "Cartão não encontrado."}]
    assert _register(other_client, line["id"], theirs["id"]).status_code == 404
