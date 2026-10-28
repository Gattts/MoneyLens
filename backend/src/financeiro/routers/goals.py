from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financeiro.db import DbSession
from financeiro.deps import get_today
from financeiro.domain.goals import goal_progress
from financeiro.models import Goal, Transaction
from financeiro.schemas.common import ItemId
from financeiro.schemas.goals import GoalIn, GoalOut
from financeiro.services.lookup import ensure_unique_name, get_or_404, name_key

router = APIRouter(prefix="/goals", tags=["metas"])

NOT_FOUND = "Meta não encontrada."
DUPLICATE_NAME = "Já existe uma meta com esse nome."
Today = Annotated[date, Depends(get_today)]


@router.get("")
def list_goals(session: DbSession, today: Today) -> list[GoalOut]:
    goals = sorted(session.scalars(select(Goal)).all(), key=lambda g: (g.archived, name_key(g.name)))
    saved = _saved_by_goal(session)
    return [_goal_out(goal, saved.get(goal.id, 0), today) for goal in goals]


@router.post("", status_code=201)
def create_goal(body: GoalIn, session: DbSession, today: Today) -> GoalOut:
    ensure_unique_name(session, Goal, body.name, DUPLICATE_NAME)
    goal = Goal(**body.model_dump())
    session.add(goal)
    session.commit()
    return _goal_out(goal, 0, today)


@router.put("/{item_id}")
def update_goal(item_id: ItemId, body: GoalIn, session: DbSession, today: Today) -> GoalOut:
    goal = get_or_404(session, Goal, item_id, NOT_FOUND)
    ensure_unique_name(session, Goal, body.name, DUPLICATE_NAME, exclude_id=item_id)
    for field, value in body.model_dump().items():
        setattr(goal, field, value)
    session.commit()
    return _goal_out(goal, _saved_by_goal(session).get(goal.id, 0), today)


@router.delete("/{item_id}", status_code=204)
def delete_goal(item_id: ItemId, session: DbSession) -> None:
    # Os aportes continuam como lançamentos de poupança; o banco limpa o goal_id (ON DELETE SET NULL).
    session.delete(get_or_404(session, Goal, item_id, NOT_FOUND))
    session.commit()


def _goal_out(goal: Goal, saved_cents: int, today: date) -> GoalOut:
    progress = goal_progress(goal.target_cents, saved_cents, goal.target_date, today)
    return GoalOut(
        id=goal.id,
        name=goal.name,
        icon=goal.icon,
        target_cents=goal.target_cents,
        target_date=goal.target_date,
        archived=goal.archived,
        saved_cents=saved_cents,
        remaining_cents=progress.remaining_cents,
        progress_pct=progress.progress_pct,
        months_left=progress.months_left,
        monthly_needed_cents=progress.monthly_needed_cents,
    )


def _saved_by_goal(session: Session) -> dict[int, int]:
    rows = session.execute(
        select(Transaction.goal_id, func.sum(Transaction.amount_cents))
        .where(Transaction.goal_id.is_not(None))
        .group_by(Transaction.goal_id)
    ).all()
    return {goal_id: int(total) for goal_id, total in rows if goal_id is not None}
