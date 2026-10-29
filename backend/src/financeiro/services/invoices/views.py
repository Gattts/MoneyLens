"""Respostas da API sobre importações: contagens, linhas e o total em standby."""

from datetime import timedelta

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from financeiro.domain.enums import ImportSource, LineStatus, SkipReason
from financeiro.models import CardPayment, InvoiceImport, InvoiceLine
from financeiro.schemas.invoices import (
    InvestmentOut,
    InvoiceImportDetailOut,
    InvoiceImportOut,
    InvoiceLineOut,
    PaymentSuggestionOut,
)
from financeiro.services.card_payments import payable_invoices
from financeiro.services.invoices.installments import DATE_TOLERANCE
from financeiro.services.invoices.statement_importer import investment_totals, matching_recurring
from financeiro.services.summary import pending_occurrences

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
        source=invoice.source,
        card_id=invoice.card_id,
        bank=invoice.bank,
        due_date=invoice.due_date,
        period_start=invoice.period_start,
        period_end=invoice.period_end,
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
    out = [InvoiceLineOut.model_validate(line) for line in lines]
    payments = dict(
        session.execute(
            select(CardPayment.line_id, CardPayment.id).where(
                CardPayment.line_id.in_([line.id for line in lines])
            )
        ).all()
    )
    for line in out:
        line.payment_id = payments.get(line.id)
    investment = None
    if invoice.source is ImportSource.ACCOUNT_STATEMENT:
        _name_recurring_duplicates(session, invoice, out)
        _suggest_card_payments(session, invoice, out)
        applied, redeemed = investment_totals(session, invoice)
        investment = InvestmentOut(applied_cents=applied, redeemed_cents=redeemed)
    return InvoiceImportDetailOut(
        **import_out(session, invoice).model_dump(), lines=out, investment=investment
    )


def _suggest_card_payments(session: Session, invoice: InvoiceImport, lines: list[InvoiceLineOut]) -> None:
    """Pagamento de fatura ainda não registrado: sugere a fatura quando só uma tem o valor exato."""
    for line in lines:
        if line.skip_reason is not SkipReason.CARD_PAYMENT or line.payment_id is not None:
            continue
        matches = [
            payable
            for payable in payable_invoices(session, invoice.user_id, line.date)
            if payable.remaining_cents == line.amount_cents
        ]
        if len(matches) == 1:
            match = matches[0]
            line.payment_suggestion = PaymentSuggestionOut(
                card_id=match.card_id,
                card_name=match.card_name,
                invoice_month=match.invoice_month,
                due_date=match.due_date,
            )


def _name_recurring_duplicates(session: Session, invoice: InvoiceImport, lines: list[InvoiceLineOut]) -> None:
    """Num possível duplicado de fixa ainda prevista, diz qual é ("Parece a fixa Salário")."""
    duplicates = [line for line in lines if line.skip_reason is SkipReason.DUPLICATE]
    if not duplicates or invoice.period_start is None or invoice.period_end is None:
        return
    start = invoice.period_start - DATE_TOLERANCE
    end = invoice.period_end + DATE_TOLERANCE + timedelta(days=1)
    pending = pending_occurrences(session, start, end, invoice.user_id)
    for line in duplicates:
        occurrence = matching_recurring(pending, line.is_credit, line.amount_cents, line.date)
        line.duplicate_of = occurrence.rule.description if occurrence else None


def standby_totals(session: Session, user_id: int) -> tuple[int, int]:
    count, cents = session.execute(
        select(func.count(InvoiceLine.id), func.coalesce(func.sum(InvoiceLine.amount_cents), 0))
        .join(InvoiceImport, InvoiceImport.id == InvoiceLine.import_id)
        .where(IS_PENDING, InvoiceImport.user_id == user_id)
    ).one()
    return count, cents
