"""Grava uma fatura lida e decide a situação de cada linha: fora, identificada ou em standby."""

from datetime import date, timedelta

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financeiro.domain.enums import LineStatus, SkipReason
from financeiro.domain.invoices import ParsedInvoice, ParsedLine, credit_reasons
from financeiro.domain.merchants import merchant_key
from financeiro.domain.months import add_months, clamp_day
from financeiro.domain.rules import RuleView, find_rule
from financeiro.models import Category, CategoryRule, CreditCard, InvoiceImport, InvoiceLine, Transaction

DATE_TOLERANCE = timedelta(days=3)
CENT_TOLERANCE = 1
TEXT_LIMIT = 200


def find_import(session: Session, card_id: int, due_date: date) -> InvoiceImport | None:
    query = select(InvoiceImport).where(InvoiceImport.card_id == card_id, InvoiceImport.due_date == due_date)
    return session.scalar(query)


def load_rules(session: Session) -> list[RuleView]:
    """Regras cujas categorias estão ativas (uma categoria arquivada não recebe compras novas)."""
    rows = session.execute(
        select(CategoryRule.id, CategoryRule.pattern, CategoryRule.match_type, CategoryRule.category_id)
        .join(Category, Category.id == CategoryRule.category_id)
        .where(Category.archived.is_(False))
    ).all()
    return [RuleView(*row) for row in rows]


def import_invoice(session: Session, card: CreditCard, parsed: ParsedInvoice) -> tuple[InvoiceImport, bool]:
    """Grava a fatura e as linhas; a mesma fatura (cartão + vencimento) devolve a já gravada, com False."""
    existing = find_import(session, card.id, parsed.due_date)
    if existing is not None:
        return existing, False
    invoice = InvoiceImport(
        card_id=card.id,
        bank=parsed.bank,
        due_date=parsed.due_date,
        total_cents=sum(section.total_cents for section in parsed.cards),
    )
    try:
        session.add(invoice)
        session.flush()
        rules, reasons = load_rules(session), credit_reasons(parsed.lines)
        session.add_all(
            _line(session, invoice, line, reasons.get(line.position), rules) for line in parsed.lines
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
    reason: SkipReason | None,
    rules: list[RuleView],
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
    reason = reason or _skip_reason(session, invoice.card_id, line)
    if reason is not None:
        return InvoiceLine(**fields, status=LineStatus.SKIPPED, skip_reason=reason)
    rule = find_rule(key, rules)
    if rule is None:
        return InvoiceLine(**fields, status=LineStatus.PENDING)
    return InvoiceLine(**fields, status=LineStatus.IDENTIFIED, category_id=rule.category_id, rule_id=rule.id)


def _skip_reason(session: Session, card_id: int, line: ParsedLine) -> SkipReason | None:
    if line.installment_number is not None:
        existing = find_existing_installment(session, card_id, line)
        if existing is not None:
            existing.amount_cents = line.amount_cents  # corrige o centavo que a divisão do app arredondou
            return SkipReason.EXISTING_INSTALLMENT
    if is_possible_duplicate(session, card_id, line):
        return SkipReason.DUPLICATE
    return None


def find_existing_installment(session: Session, card_id: int, line: ParsedLine) -> Transaction | None:
    """A parcela k de N já lançada no cartão (à mão ou por fatura anterior), com até 1 centavo de diferença.

    O Inter mostra a data original da compra; por segurança aceita também a data da cobrança da parcela.
    """
    number, total = line.installment_number, line.installment_total
    if number is None or total is None:
        return None
    expected = [clamp_day(add_months(line.date, number - 1), line.date.day), line.date]
    candidates = session.scalars(
        select(Transaction).where(
            Transaction.card_id == card_id,
            Transaction.installment_number == number,
            Transaction.installment_total == total,
            Transaction.amount_cents.between(
                line.amount_cents - CENT_TOLERANCE, line.amount_cents + CENT_TOLERANCE
            ),
            Transaction.date.between(min(expected) - DATE_TOLERANCE, max(expected) + DATE_TOLERANCE),
        )
    ).all()
    return next(
        (tx for tx in candidates if any(abs(tx.date - day) <= DATE_TOLERANCE for day in expected)),
        None,
    )


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
