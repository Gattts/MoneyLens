"""Tetos de gasto: a situação de cada teto no mês e os alertas de marco (50/90/100%) e de "vai estourar".

`check_limits` é a conferência única: roda antes do commit de toda ação que muda despesas e nas leituras de
tetos e alertas. Cada tipo de alerta existe uma vez só por teto e mês; numa conferência, cada teto gera no
máximo um aviso visível (o mais grave) e os outros marcos novos ficam gravados em silêncio.
"""

import logging
from dataclasses import dataclass
from datetime import date
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from financeiro.domain.enums import Kind, LimitAlertKind
from financeiro.domain.months import first_day
from financeiro.forecast.predict import ALERT_FROM_DAY, forecast_month
from financeiro.models import Category, LimitAlert, SpendingLimit, Transaction
from financeiro.services.ownership import owned

logger = logging.getLogger(__name__)

MARKS = (
    (50, LimitAlertKind.REACHED_50),
    (90, LimitAlertKind.REACHED_90),
    (100, LimitAlertKind.REACHED_100),
)
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
    spent_cents: int
    percent: int
    p50_cents: int | None
    will_exceed: bool
    active: bool


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
    actives = [_is_active(category) for _, category in rows]
    p50 = _safe_forecast(session, user_id, today) if with_forecast and any(actives) else {}
    statuses = []
    for (limit, category), active in zip(rows, actives, strict=True):
        spent_cents = spent.get(category.id, 0)
        p50_cents = p50.get(category.id)
        statuses.append(
            LimitStatus(
                limit=limit,
                category=category,
                spent_cents=spent_cents,
                percent=spent_cents * 100 // limit.amount_cents,
                p50_cents=p50_cents,
                will_exceed=LimitAlertKind.FORECAST
                in reached_kinds(spent_cents, limit.amount_cents, p50_cents, today),
                active=active,
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
        amount = status.limit.amount_cents
        new = reached_kinds(status.spent_cents, amount, status.p50_cents, today) - existing.get(
            status.limit.id, set()
        )
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
    )
    return bool(session.execute(statement).rowcount)  # type: ignore[attr-defined]


def check_limits(session: Session, user_id: int, today: date) -> None:
    statuses = limit_statuses(session, user_id, today, with_forecast=today.day >= ALERT_FROM_DAY)
    record_alerts(session, user_id, statuses, today)


def reset_month(session: Session, limit: SpendingLimit, today: date) -> None:
    """Mudar o valor do teto recomeça os alertas do mês dele."""
    session.execute(
        delete(LimitAlert).where(LimitAlert.limit_id == limit.id, LimitAlert.month == first_day(today))
    )


def _is_active(category: Category) -> bool:
    return category.kind is Kind.EXPENSE and not category.archived


def _safe_forecast(session: Session, user_id: int, today: date) -> dict[int, int]:
    # A previsão é consultiva: se ela falhar, os marcos de percentual continuam valendo.
    try:
        return forecast_p50(session, user_id, today)
    except Exception:
        logger.exception("Previsão indisponível para os tetos de gasto")
        return {}
