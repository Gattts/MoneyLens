"""O histórico que a previsão enxerga: despesas do usuário e fixas ainda não confirmadas."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind
from financeiro.domain.months import month_bounds
from financeiro.models import Transaction
from financeiro.services.ownership import owned
from financeiro.services.summary import pending_occurrences


@dataclass(frozen=True)
class Expense:
    date: date
    category_id: int
    amount_cents: int
    fixed: bool  # veio de uma fixa (conta que se repete todo mês)


def load_history(session: Session, user_id: int, until: date) -> list[Expense]:
    """Despesas do usuário com data anterior a `until`."""
    query = owned(Transaction, user_id).where(Transaction.kind == Kind.EXPENSE, Transaction.date < until)
    return [
        Expense(tx.date, tx.category_id, tx.amount_cents, tx.recurring_rule_id is not None)
        for tx in session.scalars(query).all()
    ]


def pending_fixed(session: Session, user_id: int, month: date, after: date) -> dict[int, int]:
    """Fixas de despesa ainda não confirmadas no mês, com data depois de `after`, por categoria."""
    start, end = month_bounds(month)
    totals: dict[int, int] = defaultdict(int)
    for occurrence in pending_occurrences(session, start, end, user_id):
        if occurrence.rule.kind is Kind.EXPENSE and occurrence.date > after:
            totals[occurrence.rule.category_id] += occurrence.rule.amount_cents
    return dict(totals)
