"""Transforma linhas da fatura em lançamentos (com as parcelas futuras) e desfaz uma importação."""

from typing import Any, cast
from uuid import uuid4

from sqlalchemy import CursorResult, delete, func, or_, select, update
from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind, LineStatus, PaymentMethod
from financeiro.domain.installments import installment_dates
from financeiro.errors import conflict
from financeiro.models import Category, InvoiceImport, InvoiceLine, Transaction

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
        group = uuid4().hex
        dates = installment_dates(line.date, total)[number - 1 :]
        created = [
            Transaction(
                **common, date=day, installment_group=group, installment_number=index, installment_total=total
            )
            for index, day in enumerate(dates, start=number)
        ]
        line.created_installment_group = group
    else:
        created = [Transaction(**common, date=line.date)]
    session.add_all(created)
    session.flush()
    line.transaction_id = created[0].id


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
    session.commit()


def undo_import(session: Session, invoice: InvoiceImport) -> None:
    """Descarta a leitura; se já confirmada, apaga também os lançamentos que ela criou, parcelas inclusive."""
    if invoice.confirmed_at is not None:
        of_this_import = InvoiceLine.import_id == invoice.id
        created_ids = select(InvoiceLine.transaction_id).where(
            of_this_import, InvoiceLine.transaction_id.is_not(None)
        )
        created_groups = select(InvoiceLine.created_installment_group).where(
            of_this_import, InvoiceLine.created_installment_group.is_not(None)
        )
        session.execute(
            delete(Transaction).where(
                or_(Transaction.id.in_(created_ids), Transaction.installment_group.in_(created_groups))
            )
        )
    session.delete(invoice)
    session.commit()
