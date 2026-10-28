from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from financeiro.db import DbSession
from financeiro.deps import get_today
from financeiro.domain.months import first_day
from financeiro.schemas.common import MAX_DATE, MIN_DATE, Month
from financeiro.schemas.summary import MonthSummaryOut, YearSummaryOut
from financeiro.security import CurrentUser
from financeiro.services.summary import month_summary, year_summary

router = APIRouter(prefix="/summary", tags=["resumos"])

Today = Annotated[date, Depends(get_today)]


@router.get("/month")
def get_month_summary(
    session: DbSession, today: Today, user: CurrentUser, month: Annotated[Month | None, Query()] = None
) -> MonthSummaryOut:
    return month_summary(session, month or first_day(today), user.id)


@router.get("/year")
def get_year_summary(
    session: DbSession,
    user: CurrentUser,
    today: Today,
    year: Annotated[int | None, Query(ge=MIN_DATE.year, le=MAX_DATE.year)] = None,
) -> YearSummaryOut:
    return year_summary(session, year or today.year, user.id)
