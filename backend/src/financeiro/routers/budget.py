from fastapi import APIRouter

from financeiro.db import DbSession
from financeiro.errors import AppError
from financeiro.models import BudgetSettings
from financeiro.schemas.budget import BudgetSettingsIn, BudgetSettingsOut
from financeiro.services.summary import get_plan

router = APIRouter(prefix="/budget-settings", tags=["orçamento"])

TOTAL_PCT = 100


@router.get("")
def get_budget_settings(session: DbSession) -> BudgetSettingsOut:
    plan = get_plan(session)
    return BudgetSettingsOut(needs_pct=plan.needs_pct, wants_pct=plan.wants_pct, savings_pct=plan.savings_pct)


@router.put("")
def update_budget_settings(body: BudgetSettingsIn, session: DbSession) -> BudgetSettingsOut:
    total = body.needs_pct + body.wants_pct + body.savings_pct
    if total != TOTAL_PCT:
        raise AppError(f"Os percentuais precisam somar 100% (agora somam {total}%).", 422)
    settings = session.get(BudgetSettings, 1) or BudgetSettings(id=1)
    settings.needs_pct, settings.wants_pct, settings.savings_pct = (
        body.needs_pct,
        body.wants_pct,
        body.savings_pct,
    )
    session.add(settings)
    session.commit()
    return BudgetSettingsOut.model_validate(settings)
