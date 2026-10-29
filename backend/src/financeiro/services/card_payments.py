"""Pagamentos das faturas: registrar, excluir e quanto já foi pago em cada fatura."""

from dataclasses import dataclass
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financeiro.domain.cards import due_date, invoice_month_for, invoice_period
from financeiro.domain.enums import ImportSource, PaymentSource, SkipReason
from financeiro.domain.months import add_months
from financeiro.errors import conflict, invalid
from financeiro.models import CardPayment, CreditCard, InvoiceImport, InvoiceLine, Transaction
from financeiro.schemas.cards import CardPaymentIn
from financeiro.services.ownership import get_owned, owned

NOT_CLOSED = "Esta fatura ainda não fechou."
BEFORE_PERIOD = "A data é anterior ao período desta fatura."
FROM_INVOICE = "Desfaça a importação da fatura para tirar este pagamento."
PAYMENT_EXISTS = "Este pagamento já foi registrado. Exclua o pagamento antes."
NOT_A_PAYMENT = "Esta linha não é um pagamento de fatura."
CARD_NOT_FOUND = "Cartão não encontrado."
# Pagamento que aparece no extrato até 5 dias depois do vencimento ainda é sugerido para a fatura.
SUGGESTION_GRACE = timedelta(days=5)


@dataclass(frozen=True)
class PayableInvoice:
    card_id: int
    card_name: str
    invoice_month: date
    due_date: date
    remaining_cents: int


def sum_purchases(session: Session, card_id: int, start: date, end: date | None = None) -> int:
    query = select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
        Transaction.card_id == card_id, Transaction.date >= start
    )
    if end is not None:
        query = query.where(Transaction.date < end)
    return int(session.scalar(query) or 0)


def payable_invoices(session: Session, user_id: int, day: date) -> list[PayableInvoice]:
    """Faturas que um pagamento feito em `day` pode quitar: fechadas, com saldo e perto do vencimento."""
    payable: list[PayableInvoice] = []
    for card in session.scalars(owned(CreditCard, user_id)).all():
        paid = paid_by_month(session, card.id)
        month = add_months(invoice_month_for(day, card.closing_day), -1)  # a última que fechou até `day`
        while (due := due_date(month, card.closing_day, card.due_day)) + SUGGESTION_GRACE >= day:
            start, end = invoice_period(month, card.closing_day)
            remaining = sum_purchases(session, card.id, start, end) - paid.get(month, (0, day))[0]
            if due >= card.payments_since and remaining > 0:
                payable.append(PayableInvoice(card.id, card.name, month, due, remaining))
            month = add_months(month, -1)
    return payable


def register_line_payment(
    session: Session, line: InvoiceLine, *, user_id: int, card_id: int, invoice_month: date
) -> CardPayment:
    """Confirma a linha do extrato como pagamento da fatura escolhida (data e valor da linha)."""
    statement = session.get_one(InvoiceImport, line.import_id)
    if (
        statement.source is not ImportSource.ACCOUNT_STATEMENT
        or line.skip_reason is not SkipReason.CARD_PAYMENT
    ):
        raise conflict(NOT_A_PAYMENT)
    card = get_owned(session, CreditCard, card_id, user_id)
    if card is None:
        raise invalid("card_id", CARD_NOT_FOUND)
    if line.date < invoice_period(invoice_month, card.closing_day)[1]:
        raise invalid("invoice_month", NOT_CLOSED)
    if line_payment(session, line.id) is not None:
        raise conflict(PAYMENT_EXISTS)
    payment = CardPayment(
        user_id=user_id,
        card_id=card.id,
        invoice_month=invoice_month,
        paid_on=line.date,
        amount_cents=line.amount_cents,
        source=PaymentSource.ACCOUNT_STATEMENT,
        line_id=line.id,
    )
    try:
        session.add(payment)
        session.commit()
    except IntegrityError as error:  # dois cliques quase juntos: a unicidade de line_id barra o segundo
        session.rollback()
        raise conflict(PAYMENT_EXISTS) from error
    return payment


def line_payment(session: Session, line_id: int) -> CardPayment | None:
    return session.scalar(select(CardPayment).where(CardPayment.line_id == line_id))


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
