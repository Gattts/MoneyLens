"""Transforma linhas da fatura em lançamentos (com as parcelas futuras) e desfaz uma importação."""

from typing import Any, cast
from uuid import uuid4

from sqlalchemy import CursorResult, delete, func, or_, select, update
from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind, LineStatus, PaymentMethod, SkipReason
from financeiro.domain.installments import installment_dates
from financeiro.errors import conflict
from financeiro.models import Category, InvoiceImport, InvoiceLine, Transaction
from financeiro.services.invoices.installments import is_linked, series_parcels

DESCRIPTION_LIMIT = 120
ALREADY_HANDLED = "Esta linha já foi importada ou está fora da importação."


def changed_rows(result: object) -> int:
    return cast(CursorResult[Any], result).rowcount


def post_line(session: Session, invoice: InvoiceImport, line: InvoiceLine) -> None:
    """Cria o lançamento da linha identificada; numa parcela k de N, cria as parcelas k até N."""
    # A troca identified -> imported é condicional: dois pedidos simultâneos não lançam a mesma linha 2 vezes.
    claimed = session.execute(
        update(InvoiceLine)
        .where(InvoiceLine.id == line.id, InvoiceLine.status == LineStatus.IDENTIFIED)
        .values(status=LineStatus.IMPORTED)
    )
    if changed_rows(claimed) == 0:
        raise conflict(ALREADY_HANDLED)
    category = session.get_one(Category, line.category_id)
    common = {
        "user_id": invoice.user_id,
        "description": line.description[:DESCRIPTION_LIMIT],
        "kind": Kind.EXPENSE,
        "amount_cents": line.amount_cents,
        "category_id": category.id,
        "bucket": category.default_bucket,
        "payment_method": PaymentMethod.CREDIT_CARD,
        "card_id": invoice.card_id,
        "notes": f"Importado da fatura {invoice.bank.capitalize()} (venc. {invoice.due_date:%d/%m/%Y})",
    }
    number, total = line.installment_number, line.installment_total
    if number is not None and total is not None:
        existing = series_parcels(session, invoice.card_id, line)
        if number in existing:
            # Outra fatura (ou um lançamento à mão) já criou esta parcela: a linha só aponta para ela.
            _mark_existing(session, line, existing[number])
            return
        group = uuid4().hex
        dates = installment_dates(line.date, total)
        created = [
            Transaction(
                **common,
                date=dates[index - 1],
                installment_group=group,
                installment_number=index,
                installment_total=total,
            )
            for index in range(number, total + 1)
            if index not in existing  # parcelas futuras que outra fatura já criou não são duplicadas
        ]
        line.created_installment_group = group
    else:
        created = [Transaction(**common, date=line.date)]
    session.add_all(created)
    session.flush()
    line.transaction_id = created[0].id


def _mark_existing(session: Session, line: InvoiceLine, parcel: Transaction) -> None:
    parcel.amount_cents = line.amount_cents  # corrige o centavo que a divisão do app arredondou
    line.status, line.skip_reason = LineStatus.SKIPPED, SkipReason.EXISTING_INSTALLMENT
    if not is_linked(session, parcel.id):
        line.transaction_id = parcel.id
    session.flush()


def confirm_import(session: Session, invoice: InvoiceImport) -> None:
    claimed = session.execute(
        update(InvoiceImport)
        .where(InvoiceImport.id == invoice.id, InvoiceImport.confirmed_at.is_(None))
        .values(confirmed_at=func.now())
    )
    if changed_rows(claimed) == 0:
        raise conflict("Esta fatura já foi confirmada.")
    session.refresh(invoice)
    identified = session.scalars(
        select(InvoiceLine)
        .where(InvoiceLine.import_id == invoice.id, InvoiceLine.status == LineStatus.IDENTIFIED)
        .order_by(InvoiceLine.position)
    ).all()
    for line in identified:
        post_line(session, invoice, line)
    # Parcelas reconhecidas na leitura: o valor da fatura vale (corrige o centavo do arredondamento).
    known_parcels = session.execute(
        select(InvoiceLine.amount_cents, Transaction)
        .join(Transaction, Transaction.id == InvoiceLine.transaction_id)
        .where(
            InvoiceLine.import_id == invoice.id,
            InvoiceLine.skip_reason == SkipReason.EXISTING_INSTALLMENT,
        )
    ).all()
    for amount, parcel in known_parcels:
        parcel.amount_cents = amount
    session.commit()


def undo_import(session: Session, invoice: InvoiceImport) -> None:
    """Descarta a leitura; se confirmada, apaga o que ela lançou, menos o que outra fatura usa."""
    if invoice.confirmed_at is not None:
        mine = InvoiceLine.import_id == invoice.id
        created_ids = select(InvoiceLine.transaction_id).where(
            mine, InvoiceLine.status == LineStatus.IMPORTED, InvoiceLine.transaction_id.is_not(None)
        )
        created_groups = select(InvoiceLine.created_installment_group).where(
            mine, InvoiceLine.created_installment_group.is_not(None)
        )
        used_by_others = select(InvoiceLine.transaction_id).where(
            InvoiceLine.import_id != invoice.id, InvoiceLine.transaction_id.is_not(None)
        )
        session.execute(
            delete(Transaction).where(
                or_(Transaction.id.in_(created_ids), Transaction.installment_group.in_(created_groups)),
                Transaction.id.not_in(used_by_others),
            )
        )
    session.delete(invoice)
    session.commit()
