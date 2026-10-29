"""Uso do limite e faturas de um cartão, calculados a partir dos lançamentos e dos pagamentos registrados."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financeiro.domain.cards import (
    due_date,
    invoice_month_for,
    invoice_period,
    invoice_status,
    open_invoice_start,
    tracked_closed_months,
)
from financeiro.models import CreditCard, Transaction
from financeiro.schemas.cards import CardOut, CardPaymentOut, InvoiceOut, InvoiceSummary
from financeiro.schemas.transactions import TransactionOut
from financeiro.services.card_payments import paid_by_month, payments_of

type Paid = dict[date, tuple[int, date]]


def card_out(session: Session, card: CreditCard, today: date) -> CardOut:
    paid = paid_by_month(session, card.id)
    used = _used(session, card, today, paid)
    current_month = invoice_month_for(today, card.closing_day)
    return CardOut(
        id=card.id,
        name=card.name,
        limit_cents=card.limit_cents,
        closing_day=card.closing_day,
        due_day=card.due_day,
        archived=card.archived,
        has_invoice_password=card.invoice_password_encrypted is not None,
        used_cents=used,
        available_cents=card.limit_cents - used,
        current_invoice=_summary(session, card, current_month, today, paid),
    )


def invoice_detail(session: Session, card: CreditCard, invoice_month: date, today: date) -> InvoiceOut:
    start, end = invoice_period(invoice_month, card.closing_day)
    purchases = session.scalars(
        select(Transaction)
        .where(Transaction.card_id == card.id, Transaction.date >= start, Transaction.date < end)
        .order_by(Transaction.date, Transaction.id)
    ).all()
    summary = _summary(session, card, invoice_month, today, paid_by_month(session, card.id))
    return InvoiceOut(
        **summary.model_dump(),
        card_id=card.id,
        period_start=start,
        period_end=end - timedelta(days=1),
        transactions=[TransactionOut.model_validate(purchase) for purchase in purchases],
        payments=[
            CardPaymentOut.model_validate(payment) for payment in payments_of(session, card.id, invoice_month)
        ],
    )


def _summary(
    session: Session, card: CreditCard, invoice_month: date, today: date, paid: Paid
) -> InvoiceSummary:
    start, end = invoice_period(invoice_month, card.closing_day)
    total = _sum_purchases(session, card.id, start, end)
    paid_cents, paid_on = paid.get(invoice_month, (0, None))
    return InvoiceSummary(
        month=invoice_month,
        closing_date=end,
        due_date=due_date(invoice_month, card.closing_day, card.due_day),
        total_cents=total,
        status=invoice_status(
            invoice_month,
            card.closing_day,
            card.due_day,
            today,
            total_cents=total,
            paid_cents=paid_cents,
            tracked_since=card.payments_since,
        ),
        paid_cents=paid_cents,
        remaining_cents=max(0, total - paid_cents),
        paid_on=paid_on,
    )


def _used(session: Session, card: CreditCard, today: date, paid: Paid) -> int:
    """Fatura aberta e parcelas futuras, mais o que falta pagar das faturas fechadas desde o marco."""
    used = _sum_purchases(session, card.id, open_invoice_start(today, card.closing_day))
    for month in tracked_closed_months(today, card.closing_day, card.due_day, card.payments_since):
        start, end = invoice_period(month, card.closing_day)
        used += max(0, _sum_purchases(session, card.id, start, end) - paid.get(month, (0, None))[0])
    return used


def _sum_purchases(session: Session, card_id: int, start: date, end: date | None = None) -> int:
    query = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.card_id == card_id, Transaction.date >= start
    )
    if end is not None:
        query = query.where(Transaction.date < end)
    return int(session.scalar(query) or 0)
