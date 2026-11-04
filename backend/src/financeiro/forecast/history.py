"""O histórico da previsão: despesas e fixas ainda não confirmadas, pelo mês de pagamento."""

import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind
from financeiro.domain.months import month_bounds
from financeiro.models import Transaction
from financeiro.services.ownership import owned
from financeiro.services.summary import pending_paid_in


@dataclass(frozen=True)
class Expense:
    date: dt.date
    month: dt.date  # mês de pagamento: no cartão, o mês em que a fatura vence
    category_id: int
    amount_cents: int
    scheduled: bool  # fixa ou parcela: já se sabe que vem


def load_history(session: Session, user_id: int, until: date) -> list[Expense]:
    """Despesas do usuário com mês de pagamento anterior a `until` (o primeiro dia de um mês)."""
    query = owned(Transaction, user_id).where(Transaction.kind == Kind.EXPENSE, Transaction.date < until)
    expenses = []
    for tx in session.scalars(query).all():
        month = tx.payment_month
        if month < until:
            scheduled = tx.recurring_rule_id is not None or tx.installment_total is not None
            expenses.append(Expense(tx.date, month, tx.category_id, tx.amount_cents, scheduled))
    return expenses


def pending_fixed(session: Session, user_id: int, month: date, after: date) -> dict[int, int]:
    """Fixas de despesa ainda não confirmadas pagas no mês, com data depois de `after`, por categoria."""
    start, end = month_bounds(month)
    totals: dict[int, int] = defaultdict(int)
    for occurrence in pending_paid_in(session, user_id, start, end).get(start, []):
        if occurrence.rule.kind is Kind.EXPENSE and occurrence.date > after:
            totals[occurrence.rule.category_id] += occurrence.rule.amount_cents
    return dict(totals)
