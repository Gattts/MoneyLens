"""Previsão do mês atual com o modelo exportado (onnxruntime): valor provável, teto e alertas."""

import hashlib
import json
import logging
from collections import defaultdict
from datetime import date

import numpy as np
import onnxruntime as ort
from sqlalchemy.orm import Session

from financeiro.domain.months import add_months, first_day
from financeiro.forecast import BASE_ONNX
from financeiro.forecast.baseline import baseline_cents
from financeiro.forecast.features import categories_to_forecast, days_in, history_months, snapshot
from financeiro.forecast.history import Expense, load_history, pending_fixed
from financeiro.forecast.store import latest_model, prefers_baseline
from financeiro.models import Category
from financeiro.schemas.forecast import CategoryForecast, ForecastOut, ForecastTotal, Source
from financeiro.services.ownership import owned

logger = logging.getLogger(__name__)
ALERT_FROM_DAY = 7  # antes disso o ritmo do mês ainda engana
ALERT_MIN_CENTS = 5_000  # gasto abaixo de R$ 50 não vira alerta
# Uma sessão do onnxruntime por modelo: (usuário, versão, hash do modelo) ou "base". O hash garante que um id
# de usuário reaproveitado (SQLite) ou um treino novo nunca recebem a sessão de outro modelo.
_cache: dict[tuple[int, int, str] | str, ort.InferenceSession] = {}


def clear_cache() -> None:
    _cache.clear()


def run_model(model: ort.InferenceSession, features: np.ndarray) -> np.ndarray:
    """Saída [N, 2]: valor provável e teto, divididos pela escala de cada categoria."""
    (out,) = model.run(["quantiles"], {"features": features})
    return np.asarray(out)


def forecast_month(session: Session, user_id: int, today: date) -> ForecastOut:
    """Previsão do mês atual pelo mês de pagamento: comprometido exato; o modelo prevê o que ainda entra."""
    month = first_day(today)
    expenses = load_history(session, user_id, until=add_months(month, 1))
    ahead = _ahead(session, user_id, expenses, month, today)
    category_ids = categories_to_forecast(expenses, month, ahead)
    model, source = _model_for(session, user_id)
    shots = [
        snapshot(expenses, category_id, month, today.day, ahead.get(category_id, 0))
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
        committed = shot.committed_cents
        baseline = baseline_cents(expenses, shot.category_id, month, today, ahead.get(shot.category_id, 0))
        # O modelo prevê só o restante (o que ainda entra); restante negativo vira zero.
        remainder = max(0, round(float(median) * shot.scale_cents))
        p50 = max(baseline, committed) if source == "statistic" else committed + remainder
        p90 = max(committed + max(0, round(float(upper) * shot.scale_cents)), p50)
        category = names[shot.category_id]
        entered = _entered(expenses, shot.category_id, month, today)
        reason = alert_reason(committed, entered, p90, today)
        lines.append(
            CategoryForecast(
                category_id=shot.category_id,
                name=category.name,
                icon=category.icon,
                spent_cents=spent,
                committed_cents=committed,
                p50_cents=p50,
                p90_cents=p90,
                baseline_cents=baseline,
                source=source,
                alert=reason is not None,
                alert_reason=reason,
            )
        )
    total = ForecastTotal(
        spent_cents=sum(line.spent_cents for line in lines),
        committed_cents=sum(line.committed_cents for line in lines),
        p50_cents=sum(line.p50_cents for line in lines),
        p90_cents=sum(line.p90_cents for line in lines),
    )
    return ForecastOut(
        month=month,
        day=today.day,
        source=source,
        history_months=len(history_months(expenses, before=month)),
        total=total,
        categories=lines,
    )


def alert_reason(committed_cents: int, entered_cents: int, p90_cents: int, today: date) -> str | None:
    """ "above": o comprometido já chegou ao máximo provável; "pace": no ritmo do mês, vai chegar.

    Só a partir do dia 7 e de R$ 50 comprometidos.
    """
    if today.day < ALERT_FROM_DAY or committed_cents < ALERT_MIN_CENTS:
        return None
    if committed_cents >= p90_cents:
        return "above"
    length = days_in(first_day(today))
    pace = committed_cents + round(entered_cents / today.day * (length - today.day))
    return "pace" if pace >= p90_cents else None


def _ahead(
    session: Session, user_id: int, expenses: list[Expense], month: date, today: date
) -> dict[int, int]:
    """O que já se sabe que vem no mês, por categoria: fixas a confirmar e lançamentos com data futura."""
    ahead: dict[int, int] = defaultdict(int, pending_fixed(session, user_id, month, after=today))
    for expense in expenses:
        if expense.month == month and expense.date > today:
            ahead[expense.category_id] += expense.amount_cents
    return dict(ahead)


def _entered(expenses: list[Expense], category_id: int, month: date, today: date) -> int:
    """Compras avulsas feitas no mês até hoje e pagas nele (o ritmo do mês)."""
    return sum(
        e.amount_cents
        for e in expenses
        if e.category_id == category_id
        and e.month == month
        and not e.scheduled
        and first_day(e.date) == month
        and e.date <= today
    )


def _model_for(session: Session, user_id: int) -> tuple[ort.InferenceSession, Source]:
    stored = latest_model(session, user_id)
    if stored is not None:
        key = (user_id, stored.version, hashlib.sha256(stored.onnx).hexdigest())
        if key not in _cache:
            try:
                _cache[key] = ort.InferenceSession(stored.onnx, providers=["CPUExecutionProvider"])
            except Exception:
                logger.warning("Modelo de previsão ilegível (usuário %s, versão %s); usando o base", *key[:2])
                return _base(), "base_model"
        # Se a estatística errou menos no teste do treino, ela dá o provável; o modelo, o máximo provável.
        return _cache[key], "statistic" if prefers_baseline(json.loads(stored.metrics)) else "model"
    return _base(), "base_model"


def _base() -> ort.InferenceSession:
    if "base" not in _cache:
        _cache["base"] = ort.InferenceSession(BASE_ONNX.read_bytes(), providers=["CPUExecutionProvider"])
    return _cache["base"]
