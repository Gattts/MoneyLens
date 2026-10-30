"""Tetos de gasto: a situação de cada teto no mês e os alertas de marco (50/90/100%) e de "vai estourar".

`check_limits` é a conferência única: roda antes do commit de toda ação que muda despesas e nas leituras de
tetos e alertas. Cada tipo de alerta existe uma vez só por teto e mês; numa conferência, cada teto gera no
máximo um aviso visível (o mais grave) e os outros marcos novos ficam gravados em silêncio.
"""

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind, LimitAlertKind
from financeiro.domain.months import first_day
from financeiro.forecast.features import HISTORY_MONTHS, category_totals, history_months
from financeiro.forecast.history import load_history
from financeiro.forecast.predict import ALERT_FROM_DAY, forecast_month
from financeiro.models import Category, LimitAlert, SpendingLimit, Transaction
from financeiro.services.ownership import owned
from financeiro.services.summary import planned_income_cents

logger = logging.getLogger(__name__)

MARKS = (
    (50, LimitAlertKind.REACHED_50),
    (90, LimitAlertKind.REACHED_90),
    (100, LimitAlertKind.REACHED_100),
)
SUGGESTION_STEP_CENTS = 1_000  # a sugestão sobe de R$ 10 em R$ 10
SEVERITY = (
    LimitAlertKind.REACHED_100,
    LimitAlertKind.FORECAST,
    LimitAlertKind.REACHED_90,
    LimitAlertKind.REACHED_50,
)


@dataclass(frozen=True)
class LimitStatus:
    limit: SpendingLimit
    category: Category
    amount_cents: int  # o teto em reais neste mês (o fixo, ou a % da renda prevista)
    income_percent: int | None
    income_cents: int | None  # a renda prevista usada (só no teto por %)
    spent_cents: int
    percent: int
    p50_cents: int | None
    will_exceed: bool
    active: bool
    no_income: bool  # teto por % num mês sem renda prevista: fica inativo


@dataclass(frozen=True)
class Suggestion:
    suggested_cents: int | None  # None: a categoria ainda não tem histórico
    low_cents: int
    high_cents: int
    months: int
    income_cents: int = 0  # renda prevista do mês, para o teto por %
    suggested_percent: int | None = None  # a sugestão em % dessa renda, arredondada para cima


def reached_kinds(
    spent_cents: int, amount_cents: int, p50_cents: int | None, today: date
) -> set[LimitAlertKind]:
    """Os alertas que a situação de hoje justifica (sem olhar os que já existem)."""
    kinds = {kind for mark, kind in MARKS if spent_cents * 100 >= amount_cents * mark}
    if (
        today.day >= ALERT_FROM_DAY
        and p50_cents is not None
        and p50_cents >= amount_cents
        and spent_cents < amount_cents
    ):
        kinds.add(LimitAlertKind.FORECAST)
    return kinds


def month_spent(session: Session, user_id: int, today: date) -> dict[int, int]:
    """Despesas de cada categoria do dia 1 até hoje (lançamento com data futura conta quando o dia chega)."""
    query = (
        select(Transaction.category_id, func.sum(Transaction.amount_cents))
        .where(
            Transaction.user_id == user_id,
            Transaction.kind == Kind.EXPENSE,
            Transaction.date >= first_day(today),
            Transaction.date <= today,
        )
        .group_by(Transaction.category_id)
    )
    return {category_id: int(total) for category_id, total in session.execute(query).all()}


def forecast_p50(session: Session, user_id: int, today: date) -> dict[int, int]:
    """Valor provável do mês de cada categoria, pela previsão."""
    return {line.category_id: line.p50_cents for line in forecast_month(session, user_id, today).categories}


def limit_statuses(session: Session, user_id: int, today: date, *, with_forecast: bool) -> list[LimitStatus]:
    rows = session.execute(
        owned(SpendingLimit, user_id)
        .join(Category, Category.id == SpendingLimit.category_id)
        .add_columns(Category)
    ).all()
    if not rows:
        return []
    spent = month_spent(session, user_id, today)
    needs_income = any(limit.income_percent is not None for limit, _ in rows)
    income = planned_income_cents(session, first_day(today), user_id) if needs_income else None
    amounts = [_amount(limit, income) for limit, _ in rows]
    actives = [
        _is_active(category) and amount > 0 for (_, category), amount in zip(rows, amounts, strict=True)
    ]
    p50 = _safe_forecast(session, user_id, today) if with_forecast and any(actives) else {}
    statuses = []
    for (limit, category), amount, active in zip(rows, amounts, actives, strict=True):
        spent_cents = spent.get(category.id, 0)
        p50_cents = p50.get(category.id)
        statuses.append(
            LimitStatus(
                limit=limit,
                category=category,
                amount_cents=amount,
                income_percent=limit.income_percent,
                income_cents=income if limit.income_percent is not None else None,
                spent_cents=spent_cents,
                percent=spent_cents * 100 // amount if amount > 0 else 0,
                p50_cents=p50_cents,
                will_exceed=amount > 0
                and LimitAlertKind.FORECAST in reached_kinds(spent_cents, amount, p50_cents, today),
                active=active,
                no_income=amount == 0,
            )
        )
    return sorted(
        statuses, key=lambda status: (not status.active, -status.percent, status.category.name.casefold())
    )


def record_alerts(session: Session, user_id: int, statuses: list[LimitStatus], today: date) -> None:
    month = first_day(today)
    existing: dict[int, set[LimitAlertKind]] = {}
    for limit_id, kind in session.execute(
        select(LimitAlert.limit_id, LimitAlert.kind).where(
            LimitAlert.user_id == user_id, LimitAlert.month == month
        )
    ).all():
        existing.setdefault(limit_id, set()).add(kind)
    for status in statuses:
        if not status.active:
            continue
        amount = status.amount_cents
        recorded = existing.get(status.limit.id, set())
        new = reached_kinds(status.spent_cents, amount, status.p50_cents, today) - recorded
        if LimitAlertKind.REACHED_100 in recorded:
            new.discard(
                LimitAlertKind.FORECAST
            )  # depois de passar do teto, "vai passar" não tem mais sentido
        if not new:
            continue
        visible = next(kind for kind in SEVERITY if kind in new)
        for kind in new:
            insert_alert(
                session,
                {
                    "user_id": user_id,
                    "limit_id": status.limit.id,
                    "month": month,
                    "kind": kind,
                    "spent_cents": status.spent_cents,
                    "limit_cents": amount,
                    "forecast_cents": status.p50_cents if kind is LimitAlertKind.FORECAST else None,
                    "silent": kind is not visible,
                },
            )


def insert_alert(session: Session, values: dict[str, Any]) -> bool:
    """Grava o alerta; se outra conferência acabou de gravar o mesmo (duas abas), não faz nada."""
    dialect = postgresql if session.get_bind().dialect.name == "postgresql" else sqlite
    statement = (
        dialect.insert(LimitAlert)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["limit_id", "month", "kind"])
        .returning(LimitAlert.id)
    )
    # RETURNING em vez de rowcount: no Postgres, o rowcount de um INSERT pela sessão não diz se inseriu.
    return session.execute(statement).first() is not None


def check_limits(session: Session, user_id: int, today: date) -> None:
    statuses = limit_statuses(session, user_id, today, with_forecast=today.day >= ALERT_FROM_DAY)
    record_alerts(session, user_id, statuses, today)


def reset_month(session: Session, limit: SpendingLimit, today: date) -> None:
    """Mudar o valor do teto recomeça os alertas do mês dele."""
    session.execute(
        delete(LimitAlert).where(LimitAlert.limit_id == limit.id, LimitAlert.month == first_day(today))
    )


def suggest_limit(session: Session, user_id: int, category_id: int, today: date) -> Suggestion:
    """Valor sugerido: o provável do mês pela previsão (ou a média recente), arredondado para cima.

    A faixa vem dos até 3 meses fechados anteriores em que a pessoa lançou alguma despesa.
    """
    month = first_day(today)
    income = planned_income_cents(session, month, user_id)
    expenses = load_history(session, user_id, until=month)
    totals = category_totals(expenses, category_id)
    values = [totals.get(past, 0) for past in history_months(expenses, before=month)[-HISTORY_MONTHS:]]
    if not any(values):
        return Suggestion(None, 0, 0, 0, income_cents=income)
    predicted = _safe_forecast(session, user_id, today).get(category_id)
    base = predicted if predicted is not None else sum(values) / len(values)
    suggested = math.ceil(base / SUGGESTION_STEP_CENTS) * SUGGESTION_STEP_CENTS
    percent = min(math.ceil(suggested * 100 / income), 100) if income > 0 else None
    return Suggestion(
        suggested, min(values), max(values), len(values), income_cents=income, suggested_percent=percent
    )


def _amount(limit: SpendingLimit, income: int | None) -> int:
    if limit.amount_cents is not None:
        return limit.amount_cents
    return (income or 0) * (limit.income_percent or 0) // 100


def _is_active(category: Category) -> bool:
    return category.kind is Kind.EXPENSE and not category.archived


def _safe_forecast(session: Session, user_id: int, today: date) -> dict[int, int]:
    # A previsão é consultiva: se ela falhar, os marcos de percentual continuam valendo. O savepoint impede
    # que um erro de SQL dentro dela aborte a transação da ação da pessoa (no Postgres, aborta tudo).
    try:
        with session.begin_nested():
            return forecast_p50(session, user_id, today)
    except Exception:
        logger.exception("Previsão indisponível para os tetos de gasto")
        return {}
