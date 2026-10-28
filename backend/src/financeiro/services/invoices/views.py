"""Respostas da API sobre importações: contagens, linhas e o total em standby."""

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from financeiro.domain.enums import LineStatus
from financeiro.models import InvoiceImport, InvoiceLine
from financeiro.schemas.invoices import InvoiceImportDetailOut, InvoiceImportOut, InvoiceLineOut

IS_PENDING = InvoiceLine.status == LineStatus.PENDING


def import_out(session: Session, invoice: InvoiceImport) -> InvoiceImportOut:
    line_count, pending_count, pending_cents = session.execute(
        select(
            func.count(InvoiceLine.id),
            func.coalesce(func.sum(case((IS_PENDING, 1), else_=0)), 0),
            func.coalesce(func.sum(case((IS_PENDING, InvoiceLine.amount_cents), else_=0)), 0),
        ).where(InvoiceLine.import_id == invoice.id)
    ).one()
    return InvoiceImportOut(
        id=invoice.id,
        card_id=invoice.card_id,
        bank=invoice.bank,
        due_date=invoice.due_date,
        total_cents=invoice.total_cents,
        confirmed_at=invoice.confirmed_at,
        created_at=invoice.created_at,
        line_count=line_count,
        pending_count=pending_count,
        pending_cents=pending_cents,
    )


def import_detail(session: Session, invoice: InvoiceImport) -> InvoiceImportDetailOut:
    lines = session.scalars(
        select(InvoiceLine).where(InvoiceLine.import_id == invoice.id).order_by(InvoiceLine.position)
    ).all()
    return InvoiceImportDetailOut(
        **import_out(session, invoice).model_dump(),
        lines=[InvoiceLineOut.model_validate(line) for line in lines],
    )


def standby_totals(session: Session) -> tuple[int, int]:
    count, cents = session.execute(
        select(func.count(InvoiceLine.id), func.coalesce(func.sum(InvoiceLine.amount_cents), 0)).where(
            IS_PENDING
        )
    ).one()
    return count, cents
