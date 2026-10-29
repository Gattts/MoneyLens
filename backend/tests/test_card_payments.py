from datetime import date

from sqlalchemy import select

from financeiro.domain.enums import PaymentSource
from financeiro.models import CardPayment, CreditCard
from tests.factories import create_card, create_category, create_transaction

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
