"""Resolver linhas em standby, aprender regras, "não lançar" e trazer de volta uma linha que ficou fora."""

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind, LineStatus, MatchType, RuleSource, SkipReason
from financeiro.domain.invoices import kind_of
from financeiro.domain.rules import RuleView, find_rule
from financeiro.errors import conflict
from financeiro.models import CategoryRule, InvoiceImport, InvoiceLine
from financeiro.services.entries import resolve_bucket
from financeiro.services.invoices.importer import load_rules
from financeiro.services.invoices.posting import ALREADY_HANDLED, changed_rows, post_line

PATTERN_LIMIT = 80
OPEN_STATUSES = (LineStatus.PENDING, LineStatus.IDENTIFIED)
# Fora da importação, mas a pessoa pode trazer de volta (as outras razões são decisões do leitor).
INCLUDABLE = (SkipReason.DUPLICATE, SkipReason.ALREADY_IMPORTED, SkipReason.IGNORED)


def resolve_line(session: Session, line: InvoiceLine, category_id: int, *, remember: bool) -> None:
    invoice = session.get_one(InvoiceImport, line.import_id)  # dona da linha: usuário e se já foi confirmada
    kind = kind_of(line.is_credit)  # entrada só aceita categoria de receita, e saída, de despesa
    resolve_bucket(session, user_id=invoice.user_id, kind=kind, category_id=category_id, bucket=None)
    rule = (
        learn_rule(session, line.merchant_key, category_id, user_id=invoice.user_id, kind=kind)
        if remember
        else None
    )
    _identify(session, line, category_id, rule.id if rule else None, allowed=OPEN_STATUSES)
    _post_if_confirmed(session, invoice, line)
    if rule is not None:
        apply_rule_to_pending(session, rule)
    session.commit()


def learn_rule(session: Session, key: str, category_id: int, *, user_id: int, kind: Kind) -> CategoryRule:
    """Cria ou atualiza a regra exata do estabelecimento (nomes longos demais viram "contém" o começo)."""
    match_type = MatchType.EXACT if len(key) <= PATTERN_LIMIT else MatchType.CONTAINS
    pattern = key[:PATTERN_LIMIT]
    rule = session.scalar(
        select(CategoryRule).where(
            CategoryRule.user_id == user_id,
            CategoryRule.kind == kind,
            CategoryRule.match_type == match_type,
            CategoryRule.pattern == pattern,
        )
    )
    if rule is None:
        rule = CategoryRule(
            user_id=user_id,
            pattern=pattern,
            match_type=match_type,
            category_id=category_id,
            kind=kind,
            source=RuleSource.LEARNED,
        )
        session.add(rule)
    else:
        rule.category_id, rule.source = category_id, RuleSource.LEARNED
    session.flush()
    return rule


def apply_rule_to_pending(session: Session, rule: CategoryRule) -> int:
    """Aplica a regra às linhas em standby de qualquer fatura; nas confirmadas, já cria os lançamentos."""
    view = RuleView(rule.id, rule.pattern, rule.match_type, rule.category_id, rule.kind)
    pending = session.execute(
        select(InvoiceLine, InvoiceImport)
        .join(InvoiceImport, InvoiceImport.id == InvoiceLine.import_id)
        .where(InvoiceImport.user_id == rule.user_id, InvoiceLine.status == LineStatus.PENDING)
    ).all()
    matching = [
        (line, invoice)
        for line, invoice in pending
        if find_rule(line.merchant_key, [view], kind_of(line.is_credit)) is not None
    ]
    for line, invoice in matching:
        _identify(session, line, rule.category_id, rule.id, allowed=(LineStatus.PENDING,))
        _post_if_confirmed(session, invoice, line)
    return len(matching)


def ignore_line(session: Session, line: InvoiceLine) -> None:
    """ "Não lançar": a linha em standby ou identificada fica fora da importação."""
    result = session.execute(
        update(InvoiceLine)
        .where(InvoiceLine.id == line.id, InvoiceLine.status.in_(OPEN_STATUSES))
        .values(status=LineStatus.SKIPPED, skip_reason=SkipReason.IGNORED, category_id=None, rule_id=None)
    )
    if changed_rows(result) == 0:
        raise conflict(ALREADY_HANDLED)
    session.commit()


def include_line(session: Session, line: InvoiceLine) -> None:
    if line.status is not LineStatus.SKIPPED or line.skip_reason not in INCLUDABLE:
        raise conflict("Esta linha não pode voltar para a importação.")
    invoice = session.get_one(InvoiceImport, line.import_id)
    rule = find_rule(line.merchant_key, load_rules(session, invoice.user_id), kind_of(line.is_credit))
    line.skip_reason = None
    if rule is None:
        line.status = LineStatus.PENDING
    else:
        line.status, line.category_id, line.rule_id = LineStatus.IDENTIFIED, rule.category_id, rule.id
    session.flush()
    if rule is not None:
        _post_if_confirmed(session, invoice, line)
    session.commit()


def _identify(
    session: Session,
    line: InvoiceLine,
    category_id: int,
    rule_id: int | None,
    *,
    allowed: tuple[LineStatus, ...],
) -> None:
    # Condicional: uma linha que outro pedido acabou de importar não volta a ser "identificada".
    result = session.execute(
        update(InvoiceLine)
        .where(InvoiceLine.id == line.id, InvoiceLine.status.in_(allowed))
        .values(status=LineStatus.IDENTIFIED, category_id=category_id, rule_id=rule_id)
    )
    if changed_rows(result) == 0:
        raise conflict(ALREADY_HANDLED)


def _post_if_confirmed(session: Session, invoice: InvoiceImport, line: InvoiceLine) -> None:
    if invoice.confirmed_at is not None:
        post_line(session, invoice, line)
