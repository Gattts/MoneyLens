"""Uso do limite e faturas de um cartão, calculados a partir dos lançamentos."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financeiro.domain.cards import (
    due_date,
    invoice_month_for,
    invoice_period,
    invoice_status,
    limit_usage_start,
)
from financeiro.models import CreditCard, Transaction
from financeiro.schemas.cards import CardOut, InvoiceOut, InvoiceSummary
from financeiro.schemas.transactions import TransactionOut


def card_out(session: Session, card: CreditCard, today: date) -> CardOut:
    used = _sum_purchases(session, card.id, limit_usage_start(today, card.closing_day, card.due_day))
    current_month = invoice_month_for(today, card.closing_day)
    start, end = invoice_period(current_month, card.closing_day)
    return CardOut(
        id=card.id,
        name=card.name,
        limit_cents=card.limit_cents,
        closing_day=card.closing_day,
        due_day=card.due_day,
        archived=card.archived,
        used_cents=used,
        available_cents=card.limit_cents - used,
        current_invoice=InvoiceSummary(
            month=current_month,
            closing_date=end,
            due_date=due_date(current_month, card.closing_day, card.due_day),
            total_cents=_sum_purchases(session, card.id, start, end),
            status=invoice_status(current_month, card.closing_day, card.due_day, today),
        ),
    )


def invoice_detail(session: Session, card: CreditCard, invoice_month: date, today: date) -> InvoiceOut:
    start, end = invoice_period(invoice_month, card.closing_day)
    purchases = session.scalars(
        select(Transaction)
        .where(Transaction.card_id == card.id, Transaction.date >= start, Transaction.date < end)
        .order_by(Transaction.date, Transaction.id)
    ).all()
    return InvoiceOut(
        card_id=card.id,
        month=invoice_month,
        period_start=start,
        period_end=end - timedelta(days=1),
        closing_date=end,
        due_date=due_date(invoice_month, card.closing_day, card.due_day),
        status=invoice_status(invoice_month, card.closing_day, card.due_day, today),
        total_cents=sum(purchase.amount_cents for purchase in purchases),
        transactions=[TransactionOut.model_validate(purchase) for purchase in purchases],
    )


def _sum_purchases(session: Session, card_id: int, start: date, end: date | None = None) -> int:
    query = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.card_id == card_id, Transaction.date >= start
    )
    if end is not None:
        query = query.where(Transaction.date < end)
    return int(session.scalar(query) or 0)
