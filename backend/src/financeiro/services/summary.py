"""Resumos do mês e do ano pelo mês de pagamento: lançamentos e fixas ainda pendentes.

Compra no cartão conta no mês em que a fatura vence: realizada se a fatura já foi paga, prevista se não.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from financeiro.domain.budget import Entry, Flow, MonthTotals, Plan, aggregate, budget_lines, thermometer
from financeiro.domain.cash import split_paid
from financeiro.domain.enums import Bucket, Kind, PaymentMethod
from financeiro.domain.months import add_months, first_day, month_bounds
from financeiro.domain.recurrence import occurrence_date, occurs_in
from financeiro.models import BudgetSettings, Category, RecurringRule, Transaction
from financeiro.schemas.summary import (
    BudgetLineOut,
    CategoryTotalOut,
    FlowOut,
    MonthSummaryOut,
    PendingOut,
    ThermometerOut,
    YearMonthOut,
    YearSummaryOut,
)
from financeiro.services.cash import (
    LOOKBACK_MONTHS,
    deferred_purchases,
    due_invoice_paid,
    transactions_paid_in,
)
from financeiro.services.ownership import owned

DEFAULT_PLAN = Plan(needs_pct=50, wants_pct=30, savings_pct=20)


@dataclass(frozen=True)
class PendingOccurrence:
    rule: RecurringRule
    date: date


def get_plan(session: Session, user_id: int) -> Plan:
    settings = session.scalar(select(BudgetSettings).where(BudgetSettings.user_id == user_id))
    if settings is None:
        return DEFAULT_PLAN
    return Plan(settings.needs_pct, settings.wants_pct, settings.savings_pct)


def month_summary(session: Session, month: date, user_id: int, today: date) -> MonthSummaryOut:
    start, end = month_bounds(month)
    transactions = transactions_paid_in(session, user_id, start, end)
    # A lista de fixas a confirmar segue a data da ocorrência; os totais, o mês de pagamento.
    listed = sorted(
        _pending_by_month(session, start, end, user_id).get(start, []),
        key=lambda occurrence: (occurrence.date, occurrence.rule.description),
    )
    counted = pending_paid_in(session, user_id, start, end).get(start, [])
    totals = aggregate(month_entries(transactions, counted, due_invoice_paid(session, user_id, start, today)))
    plan = get_plan(session, user_id)
    return MonthSummaryOut(
        month=start,
        **_period_totals(totals),
        realized_balance_cents=totals.realized_balance,
        budget=[
            BudgetLineOut(
                bucket=line.bucket,
                percent=line.percent,
                planned_cents=line.planned,
                used_cents=line.used,
                remaining_cents=line.remaining,
                used_pct=line.used_pct,
            )
            for line in budget_lines(totals, plan)
        ],
        thermometer=_thermometer(totals, plan),
        by_category=_category_totals(session, transactions, counted),
        pending=[_pending_out(occurrence) for occurrence in listed],
        deferred=deferred_purchases(session, user_id, start),
    )


def year_summary(session: Session, year: int, user_id: int, today: date) -> YearSummaryOut:
    start, end = date(year, 1, 1), date(year + 1, 1, 1)
    transactions_by_month: dict[date, list[Transaction]] = defaultdict(list)
    for transaction in transactions_paid_in(session, user_id, start, end):
        transactions_by_month[transaction.payment_month].append(transaction)
    pending_by_month = pending_paid_in(session, user_id, start, end)

    months: list[YearMonthOut] = []
    year_entries: list[Entry] = []
    for index in range(12):
        month = add_months(start, index)
        entries = month_entries(
            transactions_by_month[month],
            pending_by_month.get(month, []),
            due_invoice_paid(session, user_id, month, today),
        )
        year_entries.extend(entries)
        months.append(YearMonthOut(month=month, **_period_totals(aggregate(entries))))

    totals = aggregate(year_entries)
    return YearSummaryOut(
        year=year,
        months=months,
        **_period_totals(totals),
        thermometer=_thermometer(totals, get_plan(session, user_id)),
    )


def planned_income_cents(session: Session, month: date, user_id: int) -> int:
    """Renda prevista do mês (a do Orçamento): receitas lançadas e fixas de receita ainda a confirmar."""
    start, end = month_bounds(month)
    pending = pending_paid_in(session, user_id, start, end).get(start, [])
    transactions = transactions_paid_in(session, user_id, start, end)
    return aggregate(month_entries(transactions, pending, {})).income.total


def pending_paid_in(
    session: Session, user_id: int, start: date, end: date
) -> dict[date, list[PendingOccurrence]]:
    """Fixas ainda não confirmadas, por mês de pagamento (no cartão, o da fatura), em [start, end)."""
    by_month: dict[date, list[PendingOccurrence]] = defaultdict(list)
    for occurrences in _pending_by_month(session, add_months(start, -LOOKBACK_MONTHS), end, user_id).values():
        for occurrence in occurrences:
            paid_in = occurrence.rule.payment_month_on(occurrence.date)
            if start <= paid_in < end:
                by_month[paid_in].append(occurrence)
    return by_month


def month_entries(
    transactions: Iterable[Transaction],
    pending: Iterable[PendingOccurrence],
    paid: dict[int, tuple[int, int]],
) -> list[Entry]:
    """Valores do mês. As compras de cada cartão são realizadas na proporção já paga da fatura (`paid`)."""
    entries: list[Entry] = []
    purchases: dict[int, list[Transaction]] = defaultdict(list)
    for transaction in transactions:
        on_card = transaction.kind is Kind.EXPENSE and transaction.payment_method is PaymentMethod.CREDIT_CARD
        if on_card and transaction.card_id is not None:
            purchases[transaction.card_id].append(transaction)
        else:
            entries.append(
                Entry(transaction.kind, transaction.bucket, transaction.amount_cents, pending=False)
            )
    for card_id, items in purchases.items():
        amounts = [item.amount_cents for item in items]
        paid_cents, total_cents = paid.get(card_id, (0, sum(amounts)))
        split = split_paid(amounts, paid_cents, total_cents)
        for item, (realized, pending_part) in zip(items, split, strict=True):
            if realized:
                entries.append(Entry(item.kind, item.bucket, realized, pending=False))
            if pending_part:
                entries.append(Entry(item.kind, item.bucket, pending_part, pending=True))
    entries += [Entry(p.rule.kind, p.rule.bucket, p.rule.amount_cents, pending=True) for p in pending]
    return entries


def _transactions_between(session: Session, start: date, end: date, user_id: int) -> list[Transaction]:
    query = owned(Transaction, user_id).where(Transaction.date >= start, Transaction.date < end)
    return list(session.scalars(query).all())


def pending_occurrences(session: Session, start: date, end: date, user_id: int) -> list[PendingOccurrence]:
    """Fixas ainda não confirmadas com data em [start, end)."""
    months = _pending_by_month(session, first_day(start), add_months(first_day(end), 1), user_id)
    return [occurrence for items in months.values() for occurrence in items if start <= occurrence.date < end]


def _pending_by_month(
    session: Session, start: date, end: date, user_id: int
) -> dict[date, list[PendingOccurrence]]:
    rules = session.scalars(owned(RecurringRule, user_id)).all()
    confirmed = set(
        session.execute(
            select(Transaction.recurring_rule_id, Transaction.recurrence_month).where(
                Transaction.user_id == user_id,
                Transaction.recurring_rule_id.is_not(None),
                Transaction.recurrence_month >= start,
                Transaction.recurrence_month < end,
            )
        ).all()
    )
    pending: dict[date, list[PendingOccurrence]] = defaultdict(list)
    month = start
    while month < end:
        for rule in rules:
            if occurs_in(rule.start_month, rule.end_month, month) and (rule.id, month) not in confirmed:
                pending[month].append(PendingOccurrence(rule, occurrence_date(month, rule.day_of_month)))
        month = add_months(month, 1)
    return pending


def _entries(transactions: Iterable[Transaction], pending: Iterable[PendingOccurrence]) -> list[Entry]:
    realized = [Entry(t.kind, t.bucket, t.amount_cents, pending=False) for t in transactions]
    projected = [Entry(p.rule.kind, p.rule.bucket, p.rule.amount_cents, pending=True) for p in pending]
    return realized + projected


def _flow(flow: Flow) -> FlowOut:
    return FlowOut(realized_cents=flow.realized, pending_cents=flow.pending, total_cents=flow.total)


def _period_totals(totals: MonthTotals) -> dict[str, FlowOut | int]:
    return {
        "income": _flow(totals.income),
        "needs": _flow(totals.expenses[Bucket.NEEDS]),
        "wants": _flow(totals.expenses[Bucket.WANTS]),
        "savings": _flow(totals.expenses[Bucket.SAVINGS]),
        "balance_cents": totals.balance,
    }


def _thermometer(totals: MonthTotals, plan: Plan) -> ThermometerOut:
    status, spending_pct = thermometer(totals.income.total, totals.spending, plan)
    return ThermometerOut(status=status, spending_pct=spending_pct, limit_pct=plan.needs_pct + plan.wants_pct)


def _category_totals(
    session: Session, transactions: Iterable[Transaction], pending: Iterable[PendingOccurrence]
) -> list[CategoryTotalOut]:
    totals: dict[int, int] = defaultdict(int)
    for transaction in transactions:
        if transaction.kind is Kind.EXPENSE:
            totals[transaction.category_id] += transaction.amount_cents
    for occurrence in pending:
        if occurrence.rule.kind is Kind.EXPENSE:
            totals[occurrence.rule.category_id] += occurrence.rule.amount_cents
    if not totals:
        return []
    categories = {c.id: c for c in session.scalars(select(Category).where(Category.id.in_(totals))).all()}
    return [
        CategoryTotalOut(
            category_id=category_id,
            name=categories[category_id].name,
            icon=categories[category_id].icon,
            total_cents=total,
        )
        for category_id, total in sorted(totals.items(), key=lambda item: -item[1])
    ]


def _pending_out(occurrence: PendingOccurrence) -> PendingOut:
    rule = occurrence.rule
    return PendingOut(
        rule_id=rule.id,
        description=rule.description,
        kind=rule.kind,
        amount_cents=rule.amount_cents,
        date=occurrence.date,
        category_id=rule.category_id,
        bucket=rule.bucket,
        payment_method=rule.payment_method,
        card_id=rule.card_id,
        payment_month=rule.payment_month_on(occurrence.date),
    )
