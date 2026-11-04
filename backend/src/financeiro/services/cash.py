"""Lançamentos pelo mês de pagamento, a parte paga das faturas que vencem no mês e as compras para depois."""

from collections import defaultdict
from datetime import date

from sqlalchemy.orm import Session

from financeiro.domain.cards import invoice_period, invoice_status
from financeiro.domain.cash import CardCycle, due_invoice_month
from financeiro.domain.enums import InvoiceStatus, Kind, PaymentMethod
from financeiro.domain.months import add_months, month_bounds
from financeiro.models import CreditCard, Transaction
from financeiro.schemas.summary import DeferredOut
from financeiro.services.card_payments import paid_by_month, sum_purchases
from financeiro.services.ownership import owned

# Uma compra feita até dois meses antes ainda pode ser paga no mês (fecha no fim do mês e vence no outro).
LOOKBACK_MONTHS = 2
PAID_STATUSES = {InvoiceStatus.PAID, InvoiceStatus.PAID_BEFORE_TRACKING}


def transactions_paid_in(session: Session, user_id: int, start: date, end: date) -> list[Transaction]:
    """Lançamentos cujo mês de pagamento cai em [start, end)."""
    query = owned(Transaction, user_id).where(
        Transaction.date >= add_months(start, -LOOKBACK_MONTHS), Transaction.date < end
    )
    return [t for t in session.scalars(query).all() if start <= t.payment_month < end]


def due_invoice_paid(session: Session, user_id: int, month: date, today: date) -> dict[int, tuple[int, int]]:
    """Por cartão, (pago, total) da fatura que vence em `month`.

    Paga, ou paga antes do registro, conta inteira.
    """
    paid: dict[int, tuple[int, int]] = {}
    for card in session.scalars(owned(CreditCard, user_id)).all():
        invoice = due_invoice_month(month, CardCycle(card.closing_day, card.due_day))
        start, end = invoice_period(invoice, card.closing_day)
        total = sum_purchases(session, card.id, start, end)
        paid_cents = paid_by_month(session, card.id).get(invoice, (0, None))[0]
        status = invoice_status(
            invoice,
            card.closing_day,
            card.due_day,
            today,
            total_cents=total,
            paid_cents=paid_cents,
            tracked_since=card.payments_since,
        )
        paid[card.id] = (total, total) if status in PAID_STATUSES else (paid_cents, total)
    return paid


def deferred_purchases(session: Session, user_id: int, month: date) -> list[DeferredOut]:
    """Compras no cartão feitas no mês que só são pagas num mês seguinte, somadas por cartão e mês."""
    start, end = month_bounds(month)
    query = owned(Transaction, user_id).where(
        Transaction.date >= start,
        Transaction.date < end,
        Transaction.kind == Kind.EXPENSE,
        Transaction.payment_method == PaymentMethod.CREDIT_CARD,
    )
    totals: dict[tuple[int, date], int] = defaultdict(int)
    names: dict[int, str] = {}
    for purchase in session.scalars(query).all():
        if purchase.card is None or purchase.payment_month < end:
            continue
        totals[(purchase.card.id, purchase.payment_month)] += purchase.amount_cents
        names[purchase.card.id] = purchase.card.name
    return [
        DeferredOut(card_id=card_id, card_name=names[card_id], payment_month=paid_in, total_cents=total)
        for (card_id, paid_in), total in sorted(
            totals.items(), key=lambda item: (item[0][1], names[item[0][0]].casefold())
        )
    ]
