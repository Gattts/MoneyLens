"""Pagamentos das faturas: quanto já foi pago em cada fatura e os pagamentos de uma fatura."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financeiro.models import CardPayment


def paid_by_month(session: Session, card_id: int) -> dict[date, tuple[int, date]]:
    """Por mês de fatura: total pago e data do último pagamento."""
    rows = session.execute(
        select(CardPayment.invoice_month, func.sum(CardPayment.amount_cents), func.max(CardPayment.paid_on))
        .where(CardPayment.card_id == card_id)
        .group_by(CardPayment.invoice_month)
    ).all()
    return {month: (int(total), last) for month, total, last in rows}


def payments_of(session: Session, card_id: int, invoice_month: date) -> list[CardPayment]:
    query = (
        select(CardPayment)
        .where(CardPayment.card_id == card_id, CardPayment.invoice_month == invoice_month)
        .order_by(CardPayment.paid_on, CardPayment.id)
    )
    return list(session.scalars(query).all())
