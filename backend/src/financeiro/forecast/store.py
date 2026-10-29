"""Modelos de previsão guardados no banco: gravar uma versão nova, achar a atual e listar o histórico."""

import json
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from financeiro.forecast.features import FEATURE_VERSION
from financeiro.models import ForecastModel
from financeiro.services.ownership import owned


def save_model(
    session: Session, user_id: int, onnx: bytes, metrics: dict[str, float | int], *, trained_until: date
) -> ForecastModel:
    last = session.scalar(select(func.max(ForecastModel.version)).where(ForecastModel.user_id == user_id))
    model = ForecastModel(
        user_id=user_id,
        version=(last or 0) + 1,
        trained_until=trained_until,
        feature_version=FEATURE_VERSION,
        metrics=json.dumps(metrics),
        onnx=onnx,
    )
    session.add(model)
    session.commit()
    return model


def latest_model(session: Session, user_id: int) -> ForecastModel | None:
    """A versão mais recente feita com as medidas atuais; modelos de medidas antigas não servem mais."""
    query = (
        owned(ForecastModel, user_id)
        .where(ForecastModel.feature_version == FEATURE_VERSION)
        .order_by(ForecastModel.version.desc())
        .limit(1)
    )
    return session.scalar(query)


def list_models(session: Session, user_id: int) -> list[ForecastModel]:
    return list(session.scalars(owned(ForecastModel, user_id).order_by(ForecastModel.version.desc())).all())
