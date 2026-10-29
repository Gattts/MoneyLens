"""Grava um extrato lido e decide a situação de cada linha: fora, possível duplicado, identificada ou standby.

Fica fora o que já é contado em outro lugar: pagamento da fatura do cartão, transferência entre contas do
titular e o que outro extrato do mesmo banco já trouxe. Aplicações e resgates entram pelo líquido do período,
numa linha só.
"""

from collections import Counter
from datetime import date, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financeiro.domain.enums import ImportSource, LineStatus, PaymentMethod, SkipReason
from financeiro.domain.invoices import kind_of
from financeiro.domain.merchants import merchant_key
from financeiro.domain.rules import RuleView, find_rule
from financeiro.domain.statements import ParsedStatement, ParsedStatementLine, StatementNature
from financeiro.models import InvoiceImport, InvoiceLine, Transaction
from financeiro.services.card_payments import PayableInvoice, payable_invoices
from financeiro.services.invoices.importer import TEXT_LIMIT, load_rules
from financeiro.services.invoices.installments import DATE_TOLERANCE
from financeiro.services.summary import PendingOccurrence, pending_occurrences

SAVED_KEY = "DINHEIRO GUARDADO"
SAVED_DESCRIPTION = "Dinheiro guardado no período"
NATURE_SKIPS = {
    StatementNature.CARD_PAYMENT: SkipReason.CARD_PAYMENT,
    StatementNature.OWN_TRANSFER: SkipReason.OWN_TRANSFER,
}
type LineKey = tuple[date, int, bool, str]


def find_statement(session: Session, user_id: int, parsed: ParsedStatement) -> InvoiceImport | None:
    return session.scalar(
        select(InvoiceImport).where(
            InvoiceImport.user_id == user_id,
            InvoiceImport.bank == parsed.bank,
            InvoiceImport.period_start == parsed.period_start,
            InvoiceImport.period_end == parsed.period_end,
        )
    )


def import_statement(session: Session, user_id: int, parsed: ParsedStatement) -> tuple[InvoiceImport, bool]:
    """Grava o extrato e as linhas; o mesmo extrato (banco + período) devolve o já gravado, com False."""
    existing = find_statement(session, user_id, parsed)
    if existing is not None:
        return existing, False
    statement = InvoiceImport(
        user_id=user_id,
        source=ImportSource.ACCOUNT_STATEMENT,
        bank=parsed.bank,
        period_start=parsed.period_start,
        period_end=parsed.period_end,
        total_cents=sum(line.amount_cents for line in parsed.lines if not line.is_credit),
    )
    try:
        session.add(statement)
        session.flush()
        session.add_all(_lines(session, statement, parsed))
        session.commit()
    except IntegrityError:
        # Dois envios quase simultâneos do mesmo extrato: a restrição única barra o segundo.
        session.rollback()
        existing = find_statement(session, user_id, parsed)
        if existing is None:
            raise
        return existing, False
    return statement, True


def investment_totals(session: Session, invoice: InvoiceImport) -> tuple[int, int]:
    """Aplicado e resgatado nas linhas de investimento novas desta importação."""
    applied, redeemed = session.execute(
        select(
            func.coalesce(func.sum(InvoiceLine.amount_cents).filter(InvoiceLine.is_credit.is_(False)), 0),
            func.coalesce(func.sum(InvoiceLine.amount_cents).filter(InvoiceLine.is_credit.is_(True)), 0),
        ).where(InvoiceLine.import_id == invoice.id, InvoiceLine.skip_reason == SkipReason.INVESTMENT)
    ).one()
    return int(applied), int(redeemed)


def _lines(session: Session, statement: InvoiceImport, parsed: ParsedStatement) -> list[InvoiceLine]:
    rules = load_rules(session, statement.user_id)
    already = _already_imported(session, statement, parsed.lines)
    pending = pending_occurrences(
        session,
        parsed.period_start - DATE_TOLERANCE,
        parsed.period_end + DATE_TOLERANCE + timedelta(days=1),
        statement.user_id,
    )
    decide = _Decider(session, statement, rules, pending)
    lines = [decide.line(line, already=line.position in already) for line in parsed.lines]
    new_investments = [
        line
        for line in parsed.lines
        if line.nature is StatementNature.INVESTMENT and line.position not in already
    ]
    saved = sum(-line.amount_cents if line.is_credit else line.amount_cents for line in new_investments)
    if saved > 0:
        position = max((line.position for line in parsed.lines), default=0) + 1
        synthetic = ParsedStatementLine(
            position=position,
            date=parsed.period_end,
            nature=StatementNature.OUTFLOW,
            is_credit=False,
            counterparty="",
            description=SAVED_DESCRIPTION,
            amount_cents=saved,
            payment_method=PaymentMethod.TRANSFER,
        )
        lines.append(decide.line(synthetic, already=False, key=SAVED_KEY))
    return lines


def _key(line: ParsedStatementLine) -> str:
    return merchant_key(line.description)[:TEXT_LIMIT]


def _already_imported(
    session: Session, statement: InvoiceImport, lines: list[ParsedStatementLine]
) -> set[int]:
    """Posições das linhas que outro extrato do mesmo banco já trouxe (as primeiras de cada grupo igual)."""
    rows = session.execute(
        select(
            InvoiceLine.date,
            InvoiceLine.amount_cents,
            InvoiceLine.is_credit,
            InvoiceLine.merchant_key,
            func.count(),
        )
        .join(InvoiceImport, InvoiceImport.id == InvoiceLine.import_id)
        .where(
            InvoiceImport.user_id == statement.user_id,
            InvoiceImport.source == ImportSource.ACCOUNT_STATEMENT,
            InvoiceImport.bank == statement.bank,
            InvoiceImport.id != statement.id,
            InvoiceLine.date.between(statement.period_start, statement.period_end),
            # Linha que já era repetição de outro extrato não prova nada (contaria a mesma movimentação 2x).
            or_(InvoiceLine.skip_reason.is_(None), InvoiceLine.skip_reason != SkipReason.ALREADY_IMPORTED),
        )
        .group_by(InvoiceLine.date, InvoiceLine.amount_cents, InvoiceLine.is_credit, InvoiceLine.merchant_key)
    ).all()
    previous: Counter[LineKey] = Counter(
        {(day, cents, credit, key): count for day, cents, credit, key, count in rows}
    )
    found: set[int] = set()
    for line in lines:
        key = (line.date, line.amount_cents, line.is_credit, _key(line))
        if previous[key] > 0:
            previous[key] -= 1
            found.add(line.position)
    return found


class _Decider:
    def __init__(
        self,
        session: Session,
        statement: InvoiceImport,
        rules: list[RuleView],
        pending: list[PendingOccurrence],
    ) -> None:
        self.session, self.statement, self.rules, self.pending = session, statement, rules, pending
        self.payable: dict[date, list[PayableInvoice]] = {}

    def line(self, line: ParsedStatementLine, *, already: bool, key: str | None = None) -> InvoiceLine:
        merchant = key or _key(line)
        fields = {
            "import_id": self.statement.id,
            "position": line.position,
            "date": line.date,
            "description": line.description[:TEXT_LIMIT],
            "merchant_key": merchant,
            "amount_cents": line.amount_cents,
            "is_credit": line.is_credit,
            "payment_method": line.payment_method,
        }
        reason = self._skip_reason(line, already=already)
        if reason is not None:
            return InvoiceLine(**fields, status=LineStatus.SKIPPED, skip_reason=reason)
        rule = find_rule(merchant, self.rules, kind_of(line.is_credit))
        if rule is None:
            return InvoiceLine(**fields, status=LineStatus.PENDING)
        return InvoiceLine(
            **fields, status=LineStatus.IDENTIFIED, category_id=rule.category_id, rule_id=rule.id
        )

    def _skip_reason(self, line: ParsedStatementLine, *, already: bool) -> SkipReason | None:
        if line.nature in NATURE_SKIPS:
            return NATURE_SKIPS[line.nature]
        if already:
            return SkipReason.ALREADY_IMPORTED
        if line.nature is StatementNature.INVESTMENT:
            return SkipReason.INVESTMENT
        if self._looks_like_card_payment(line):
            return SkipReason.CARD_PAYMENT
        if self._manual_duplicate(line) or matching_recurring(
            self.pending, line.is_credit, line.amount_cents, line.date
        ):
            return SkipReason.DUPLICATE
        return None

    def _looks_like_card_payment(self, line: ParsedStatementLine) -> bool:
        """Pix ou transferência que sai com o valor exato do que falta numa fatura perto do vencimento."""
        if line.is_credit or line.nature is not StatementNature.OUTFLOW:
            return False
        if line.payment_method not in (PaymentMethod.PIX, PaymentMethod.TRANSFER):
            return False
        if line.date not in self.payable:
            self.payable[line.date] = payable_invoices(self.session, self.statement.user_id, line.date)
        return any(invoice.remaining_cents == line.amount_cents for invoice in self.payable[line.date])

    def _manual_duplicate(self, line: ParsedStatementLine) -> bool:
        """Lançamento feito à mão fora do cartão, mesmo tipo e valor, em data próxima."""
        imported = select(InvoiceLine.transaction_id).where(InvoiceLine.transaction_id.is_not(None))
        query = select(Transaction.id).where(
            Transaction.user_id == self.statement.user_id,
            Transaction.card_id.is_(None),
            Transaction.kind == kind_of(line.is_credit),
            Transaction.amount_cents == line.amount_cents,
            Transaction.date.between(line.date - DATE_TOLERANCE, line.date + DATE_TOLERANCE),
            Transaction.id.not_in(imported),
        )
        return self.session.scalar(query.limit(1)) is not None


def matching_recurring(
    pending: list[PendingOccurrence], is_credit: bool, amount_cents: int, day: date
) -> PendingOccurrence | None:
    """Fixa ainda não confirmada do mesmo tipo e valor, com data próxima (o salário previsto, por exemplo)."""
    kind = kind_of(is_credit)
    return next(
        (
            occurrence
            for occurrence in pending
            if occurrence.rule.kind == kind
            and occurrence.rule.amount_cents == amount_cents
            and abs(occurrence.date - day) <= DATE_TOLERANCE
        ),
        None,
    )
