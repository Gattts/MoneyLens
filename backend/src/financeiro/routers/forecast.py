import json
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from financeiro.db import DbSession
from financeiro.deps import get_today
from financeiro.forecast.predict import forecast_month
from financeiro.forecast.store import latest_model, list_models
from financeiro.schemas.forecast import ForecastModelOut, ForecastOut
from financeiro.security import CurrentUser

router = APIRouter(prefix="/forecast", tags=["previsão"])
Today = Annotated[date, Depends(get_today)]


@router.get("")
def month_forecast(session: DbSession, user: CurrentUser, today: Today) -> ForecastOut:
    """Previsão do mês atual por categoria (valor provável, teto e alertas)."""
    return forecast_month(session, user.id, today)


@router.get("/models")
def models(session: DbSession, user: CurrentUser) -> list[ForecastModelOut]:
    """Histórico de treinos do usuário, com as métricas de cada versão (sem o modelo em si)."""
    active = latest_model(session, user.id)
    return [
        ForecastModelOut(
            version=model.version,
            trained_at=model.trained_at,
            trained_until=model.trained_until,
            feature_version=model.feature_version,
            metrics=json.loads(model.metrics),
            active=active is not None and model.id == active.id,
        )
        for model in list_models(session, user.id)
    ]
