"""Pagamentos das faturas: registrar, excluir e quanto já foi pago em cada fatura."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financeiro.domain.cards import invoice_period
from financeiro.domain.enums import PaymentSource
from financeiro.errors import conflict, invalid
from financeiro.models import CardPayment, CreditCard
from financeiro.schemas.cards import CardPaymentIn

NOT_CLOSED = "Esta fatura ainda não fechou."
BEFORE_PERIOD = "A data é anterior ao período desta fatura."
FROM_INVOICE = "Desfaça a importação da fatura para tirar este pagamento."


def record_manual_payment(
    session: Session, card: CreditCard, body: CardPaymentIn, today: date
) -> CardPayment:
    start, end = invoice_period(body.invoice_month, card.closing_day)
    if today < end:
        raise invalid("invoice_month", NOT_CLOSED)
    if body.paid_on < start:
        raise invalid("paid_on", BEFORE_PERIOD)
    payment = CardPayment(
        user_id=card.user_id,
        card_id=card.id,
        invoice_month=body.invoice_month,
        paid_on=body.paid_on,
        amount_cents=body.amount_cents,
        source=PaymentSource.MANUAL,
    )
    session.add(payment)
    session.commit()
    return payment


def delete_payment(session: Session, payment: CardPayment) -> None:
    """O pagamento vindo da fatura seguinte só sai desfazendo aquela importação."""
    if payment.source is PaymentSource.CARD_INVOICE:
        raise conflict(FROM_INVOICE)
    session.delete(payment)
    session.commit()


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
