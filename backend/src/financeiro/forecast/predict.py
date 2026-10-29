"""Previsão do mês atual com o modelo exportado (onnxruntime): valor provável, teto e alertas."""

import logging
from datetime import date, timedelta

import numpy as np
import onnxruntime as ort
from sqlalchemy.orm import Session

from financeiro.domain.months import first_day
from financeiro.forecast import BASE_ONNX
from financeiro.forecast.baseline import baseline_cents
from financeiro.forecast.features import categories_to_forecast, days_in, snapshot
from financeiro.forecast.history import load_history, pending_fixed
from financeiro.forecast.store import latest_model
from financeiro.models import Category
from financeiro.schemas.forecast import CategoryForecast, ForecastOut, ForecastTotal, Source
from financeiro.services.ownership import owned

logger = logging.getLogger(__name__)
ALERT_FROM_DAY = 7  # antes disso o ritmo do mês ainda engana
ALERT_MIN_CENTS = 5_000  # gasto abaixo de R$ 50 não vira alerta
# Uma sessão do onnxruntime por modelo: (usuário, versão) ou "base". A versão entra na chave: um treino novo
# nunca reaproveita a sessão antiga, e um usuário nunca recebe a sessão de outro.
_cache: dict[tuple[int, int] | str, ort.InferenceSession] = {}


def clear_cache() -> None:
    _cache.clear()


def run_model(model: ort.InferenceSession, features: np.ndarray) -> np.ndarray:
    """Saída [N, 2]: valor provável e teto, divididos pela escala de cada categoria."""
    (out,) = model.run(["quantiles"], {"features": features})
    return np.asarray(out)


def forecast_month(session: Session, user_id: int, today: date) -> ForecastOut:
    month = first_day(today)
    expenses = load_history(session, user_id, until=today + timedelta(days=1))
    pending = pending_fixed(session, user_id, month, after=today)
    category_ids = categories_to_forecast(expenses, month, pending)
    model, source = _model_for(session, user_id)
    shots = [
        snapshot(expenses, category_id, month, today.day, pending.get(category_id, 0))
        for category_id in category_ids
    ]
    predicted = (
        run_model(model, np.array([shot.values for shot in shots], dtype=np.float32))
        if shots
        else np.zeros((0, 2))
    )
    names = {c.id: c for c in session.scalars(owned(Category, user_id)).all()}
    lines = []
    for shot, (median, upper) in zip(shots, predicted, strict=True):
        spent = round(shot.values[0] * shot.scale_cents)
        p50 = max(
            round(float(median) * shot.scale_cents), spent
        )  # o mês não fecha abaixo do que já foi gasto
        p90 = max(round(float(upper) * shot.scale_cents), p50)
        category = names[shot.category_id]
        reason = alert_reason(spent, p90, today)
        lines.append(
            CategoryForecast(
                category_id=shot.category_id,
                name=category.name,
                icon=category.icon,
                spent_cents=spent,
                p50_cents=p50,
                p90_cents=p90,
                baseline_cents=baseline_cents(
                    expenses, shot.category_id, month, today, pending.get(shot.category_id, 0)
                ),
                source=source,
                alert=reason is not None,
                alert_reason=reason,
            )
        )
    total = ForecastTotal(
        spent_cents=sum(line.spent_cents for line in lines),
        p50_cents=sum(line.p50_cents for line in lines),
        p90_cents=sum(line.p90_cents for line in lines),
    )
    return ForecastOut(month=month, day=today.day, source=source, total=total, categories=lines)


def alert_reason(spent_cents: int, p90_cents: int, today: date) -> str | None:
    """ "above": já passou do teto; "pace": no ritmo do mês, vai passar. Só a partir do dia 7 e de R$ 50."""
    if today.day < ALERT_FROM_DAY or spent_cents < ALERT_MIN_CENTS:
        return None
    if spent_cents >= p90_cents:
        return "above"
    pace = round(spent_cents / today.day * days_in(first_day(today)))
    return "pace" if pace >= p90_cents else None


def _model_for(session: Session, user_id: int) -> tuple[ort.InferenceSession, Source]:
    stored = latest_model(session, user_id)
    if stored is not None:
        key = (user_id, stored.version)
        if key not in _cache:
            try:
                _cache[key] = ort.InferenceSession(stored.onnx, providers=["CPUExecutionProvider"])
            except Exception:
                logger.warning("Modelo de previsão ilegível (usuário %s, versão %s); usando o base", *key)
                return _base(), "base_model"
        return _cache[key], "model"
    return _base(), "base_model"


def _base() -> ort.InferenceSession:
    if "base" not in _cache:
        _cache["base"] = ort.InferenceSession(BASE_ONNX.read_bytes(), providers=["CPUExecutionProvider"])
    return _cache["base"]
