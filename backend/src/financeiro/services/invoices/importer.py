"""Grava uma fatura lida e decide a situação de cada linha: fora, identificada ou em standby."""

from datetime import date

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financeiro.domain.enums import LineStatus, SkipReason
from financeiro.domain.invoices import ParsedInvoice, ParsedLine, credit_reasons
from financeiro.domain.merchants import merchant_key
from financeiro.domain.rules import RuleView, find_rule
from financeiro.models import Category, CategoryRule, CreditCard, InvoiceImport, InvoiceLine, Transaction
from financeiro.services.invoices.installments import DATE_TOLERANCE, is_linked, series_parcels

TEXT_LIMIT = 200


def find_import(session: Session, card_id: int, due_date: date) -> InvoiceImport | None:
    query = select(InvoiceImport).where(InvoiceImport.card_id == card_id, InvoiceImport.due_date == due_date)
    return session.scalar(query)


def load_rules(session: Session, user_id: int) -> list[RuleView]:
    """Regras cujas categorias estão ativas (uma categoria arquivada não recebe compras novas)."""
    rows = session.execute(
        select(CategoryRule.id, CategoryRule.pattern, CategoryRule.match_type, CategoryRule.category_id)
        .join(Category, Category.id == CategoryRule.category_id)
        .where(CategoryRule.user_id == user_id, Category.archived.is_(False))
    ).all()
    return [RuleView(*row) for row in rows]


def import_invoice(session: Session, card: CreditCard, parsed: ParsedInvoice) -> tuple[InvoiceImport, bool]:
    """Grava a fatura e as linhas; a mesma fatura (cartão + vencimento) devolve a já gravada, com False."""
    existing = find_import(session, card.id, parsed.due_date)
    if existing is not None:
        return existing, False
    invoice = InvoiceImport(
        user_id=card.user_id,
        card_id=card.id,
        bank=parsed.bank,
        due_date=parsed.due_date,
        total_cents=sum(section.total_cents for section in parsed.cards),
    )
    try:
        session.add(invoice)
        session.flush()
        rules, reasons = load_rules(session, card.user_id), credit_reasons(parsed.lines)
        claimed: set[int] = set()  # parcelas já ligadas a uma linha desta leitura
        session.add_all(
            _line(session, invoice, line, reason=reasons.get(line.position), rules=rules, claimed=claimed)
            for line in parsed.lines
        )
        session.commit()
    except IntegrityError:
        # Dois envios quase simultâneos da mesma fatura: a restrição única barra o segundo,
        # que recebe a importação do primeiro.
        session.rollback()
        existing = find_import(session, card.id, parsed.due_date)
        if existing is None:
            raise
        return existing, False
    return invoice, True


def _line(
    session: Session,
    invoice: InvoiceImport,
    line: ParsedLine,
    *,
    reason: SkipReason | None,
    rules: list[RuleView],
    claimed: set[int],
) -> InvoiceLine:
    key = merchant_key(line.description)[:TEXT_LIMIT]
    fields = {
        "import_id": invoice.id,
        "position": line.position,
        "date": line.date,
        "description": line.description[:TEXT_LIMIT],
        "merchant_key": key,
        "amount_cents": line.amount_cents,
        "is_credit": line.is_credit,
        "installment_number": line.installment_number,
        "installment_total": line.installment_total,
    }
    if reason is not None:
        return InvoiceLine(**fields, status=LineStatus.SKIPPED, skip_reason=reason)
    existing = _existing_parcel(session, invoice.card_id, line, claimed)
    if existing is not None:
        # A linha aponta para a parcela existente: o "desfazer" de outra fatura não a apaga por baixo dela.
        return InvoiceLine(
            **fields,
            status=LineStatus.SKIPPED,
            skip_reason=SkipReason.EXISTING_INSTALLMENT,
            transaction_id=existing or None,
        )
    if is_possible_duplicate(session, invoice.card_id, line):
        return InvoiceLine(**fields, status=LineStatus.SKIPPED, skip_reason=SkipReason.DUPLICATE)
    rule = find_rule(key, rules)
    if rule is None:
        return InvoiceLine(**fields, status=LineStatus.PENDING)
    return InvoiceLine(**fields, status=LineStatus.IDENTIFIED, category_id=rule.category_id, rule_id=rule.id)


def _existing_parcel(session: Session, card_id: int, line: ParsedLine, claimed: set[int]) -> int | None:
    """Id da parcela k já lançada (0 se existe, mas já ligada a outra linha); None se não existe."""
    if line.installment_number is None:
        return None
    parcel = series_parcels(session, card_id, line).get(line.installment_number)
    if parcel is None:
        return None
    if parcel.id in claimed or is_linked(session, parcel.id):
        return 0
    claimed.add(parcel.id)
    return parcel.id


def is_possible_duplicate(session: Session, card_id: int, line: ParsedLine) -> bool:
    """Lançamento feito à mão no cartão com o mesmo valor e data próxima; os vindos de faturas não contam."""
    imported = select(InvoiceLine.transaction_id).where(InvoiceLine.transaction_id.is_not(None))
    created_groups = select(InvoiceLine.created_installment_group).where(
        InvoiceLine.created_installment_group.is_not(None)
    )
    query = select(Transaction.id).where(
        Transaction.card_id == card_id,
        Transaction.amount_cents == line.amount_cents,
        Transaction.date.between(line.date - DATE_TOLERANCE, line.date + DATE_TOLERANCE),
        Transaction.id.not_in(imported),
        or_(Transaction.installment_group.is_(None), Transaction.installment_group.not_in(created_groups)),
    )
    return session.scalar(query.limit(1)) is not None
