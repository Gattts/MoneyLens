"""Tetos de gasto por categoria e os alertas deles. As leituras também conferem os tetos (virada do dia)."""

import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.deps import Today
from financeiro.domain.enums import Kind
from financeiro.errors import conflict, invalid
from financeiro.models import Category, LimitAlert, SpendingLimit
from financeiro.schemas.common import MAX_ID, ItemId, Month
from financeiro.schemas.limits import (
    AlertOut,
    AlertsOut,
    AlertsReadIn,
    LimitIn,
    LimitOut,
    LimitUpdate,
    SuggestionOut,
)
from financeiro.security import CurrentUser
from financeiro.services.limits import (
    LimitStatus,
    check_limits,
    limit_statuses,
    record_alerts,
    reset_months,
    suggest_limit,
)
from financeiro.services.ownership import get_owned_or_404, owned

limits_router = APIRouter(prefix="/limits", tags=["tetos"])
alerts_router = APIRouter(prefix="/alerts", tags=["tetos"])

NOT_FOUND = "Teto não encontrado."
CATEGORY_NOT_FOUND = "Categoria não encontrada."
ONLY_EXPENSE = "Só categorias de despesa ativas têm teto."
DUPLICATE = "Esta categoria já tem teto."
RECENT_ALERTS = 20
CategoryId = Annotated[int, Query(gt=0, le=MAX_ID)]


@limits_router.get("")
def list_limits(
    session: DbSession, user: CurrentUser, today: Today, month: Annotated[Month | None, Query()] = None
) -> list[LimitOut]:
    """Tetos com o gasto pago no mês (padrão: o atual), a previsão e a situação; grava os alertas novos."""
    statuses = _checked_statuses(session, user.id, today, month)
    session.commit()
    return [_limit_out(status) for status in statuses]


@limits_router.post("", status_code=201)
def create_limit(body: LimitIn, session: DbSession, user: CurrentUser, today: Today) -> LimitOut:
    category = get_owned_or_404(session, Category, body.category_id, user.id, CATEGORY_NOT_FOUND)
    if category.kind is not Kind.EXPENSE or category.archived:
        raise invalid("category_id", ONLY_EXPENSE)
    if session.scalar(owned(SpendingLimit, user.id).where(SpendingLimit.category_id == category.id)):
        raise conflict(DUPLICATE)
    limit = SpendingLimit(
        user_id=user.id,
        category_id=category.id,
        amount_cents=body.amount_cents,
        income_percent=body.income_percent,
    )
    session.add(limit)
    session.flush()
    out = _limit_out(_status_of(_checked_statuses(session, user.id, today), limit.id))
    session.commit()
    return out


@limits_router.put("/{item_id}")
def update_limit(
    item_id: ItemId, body: LimitUpdate, session: DbSession, user: CurrentUser, today: Today
) -> LimitOut:
    """Mudar o valor ou a forma (R$ ou %) recomeça os alertas deste teto (mês atual e seguintes)."""
    limit = get_owned_or_404(session, SpendingLimit, item_id, user.id, NOT_FOUND)
    value = (body.amount_cents, body.income_percent)
    if value != (limit.amount_cents, limit.income_percent):  # salvar sem mudar nada não mexe nos alertas
        limit.amount_cents, limit.income_percent = value
        reset_months(session, limit, today)
        session.flush()
    out = _limit_out(_status_of(_checked_statuses(session, user.id, today), limit.id))
    session.commit()
    return out


@limits_router.delete("/{item_id}", status_code=204)
def delete_limit(item_id: ItemId, session: DbSession, user: CurrentUser) -> None:
    session.delete(get_owned_or_404(session, SpendingLimit, item_id, user.id, NOT_FOUND))
    session.commit()


@limits_router.get("/suggestion")
def suggestion(category_id: CategoryId, session: DbSession, user: CurrentUser, today: Today) -> SuggestionOut:
    """Valor sugerido para o teto da categoria, com a faixa dos últimos meses."""
    get_owned_or_404(session, Category, category_id, user.id, CATEGORY_NOT_FOUND)
    return SuggestionOut.model_validate(suggest_limit(session, user.id, category_id, today))


@alerts_router.get("")
def list_alerts(session: DbSession, user: CurrentUser, today: Today) -> AlertsOut:
    """Contagem dos não lidos e os alertas mais recentes (confere os tetos antes)."""
    check_limits(session, user.id, today)
    session.commit()
    return _alerts_out(session, user.id)


@alerts_router.post("/read")
def read_alerts(body: AlertsReadIn, session: DbSession, user: CurrentUser) -> AlertsOut:
    """Marca como lidos os alertas indicados ou, sem `ids`, todos os não lidos."""
    query = (
        update(LimitAlert)
        .where(LimitAlert.user_id == user.id, LimitAlert.read_at.is_(None), LimitAlert.silent.is_(False))
        .values(read_at=dt.datetime.now(dt.UTC))
    )
    if body.ids is not None:
        query = query.where(LimitAlert.id.in_(body.ids))
    session.execute(query)
    session.commit()
    return _alerts_out(session, user.id)


def _checked_statuses(
    session: Session, user_id: int, today: dt.date, month: dt.date | None = None
) -> list[LimitStatus]:
    # A previsão vai junto para a tela (só no mês atual); antes do dia 7 ela não gera alerta.
    statuses = limit_statuses(session, user_id, today, month=month, with_forecast=True)
    record_alerts(session, user_id, statuses, today, month)
    return statuses


def _status_of(statuses: list[LimitStatus], limit_id: int) -> LimitStatus:
    return next(status for status in statuses if status.limit.id == limit_id)


def _limit_out(status: LimitStatus) -> LimitOut:
    return LimitOut(
        id=status.limit.id,
        category_id=status.category.id,
        name=status.category.name,
        icon=status.category.icon,
        amount_cents=status.amount_cents,
        income_percent=status.income_percent,
        income_cents=status.income_cents,
        no_income=status.no_income,
        spent_cents=status.spent_cents,
        percent=status.percent,
        p50_cents=status.p50_cents,
        will_exceed=status.will_exceed,
        active=status.active,
    )


def _alerts_out(session: Session, user_id: int) -> AlertsOut:
    visible = owned(LimitAlert, user_id).where(LimitAlert.silent.is_(False))
    unread = session.scalar(
        select(func.count()).select_from(visible.where(LimitAlert.read_at.is_(None)).subquery())
    )
    rows = session.execute(
        visible.join(SpendingLimit, SpendingLimit.id == LimitAlert.limit_id)
        .join(Category, Category.id == SpendingLimit.category_id)
        .add_columns(Category)
        .order_by(LimitAlert.created_at.desc(), LimitAlert.id.desc())
        .limit(RECENT_ALERTS)
    ).all()
    items = [
        AlertOut(
            id=alert.id,
            kind=alert.kind,
            category_id=category.id,
            name=category.name,
            icon=category.icon,
            spent_cents=alert.spent_cents,
            limit_cents=alert.limit_cents,
            forecast_cents=alert.forecast_cents,
            month=alert.month,
            created_at=alert.created_at,
            read_at=alert.read_at,
        )
        for alert, category in rows
    ]
    return AlertsOut(unread=unread or 0, items=items)
