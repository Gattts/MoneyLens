"""Parcelas de uma compra parcelada que já estão lançadas no cartão (à mão ou por outra fatura)."""

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.domain.invoices import ParsedLine
from financeiro.domain.months import add_months, clamp_day
from financeiro.models import InvoiceLine, Transaction

DATE_TOLERANCE = timedelta(days=3)
CENT_TOLERANCE = 1


def series_parcels(session: Session, card_id: int, line: ParsedLine | InvoiceLine) -> dict[int, Transaction]:
    """As parcelas k até N da compra desta linha que já existem, por número.

    Casa pelo cartão, pelo total de parcelas, pelo valor (até 1 centavo de diferença) e pela data esperada
    de cada parcela. O Inter mostra a data original da compra em todas as parcelas; por segurança aceita
    também o formato em que a linha traz a data de cobrança da parcela k.
    """
    number, total = line.installment_number, line.installment_total
    if number is None or total is None:
        return {}
    bases = [line.date, clamp_day(add_months(line.date, -(number - 1)), line.date.day)]
    expected = {
        parcel: [clamp_day(add_months(base, parcel - 1), base.day) for base in bases]
        for parcel in range(number, total + 1)
    }
    candidates = session.scalars(
        select(Transaction)
        .where(
            Transaction.card_id == card_id,
            Transaction.installment_total == total,
            Transaction.installment_number.between(number, total),
            Transaction.amount_cents.between(
                line.amount_cents - CENT_TOLERANCE, line.amount_cents + CENT_TOLERANCE
            ),
        )
        .order_by(Transaction.id)
    ).all()
    found: dict[int, Transaction] = {}
    for transaction in candidates:
        parcel = transaction.installment_number
        if parcel is None or parcel in found:
            continue
        if any(abs(transaction.date - day) <= DATE_TOLERANCE for day in expected[parcel]):
            found[parcel] = transaction
    return found


def is_linked(session: Session, transaction_id: int) -> bool:
    """O lançamento já está ligado a alguma linha de fatura (cada lançamento pertence a uma linha só)."""
    query = select(InvoiceLine.id).where(InvoiceLine.transaction_id == transaction_id)
    return session.scalar(query.limit(1)) is not None
