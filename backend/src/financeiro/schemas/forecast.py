import datetime as dt
from typing import Literal

from financeiro.schemas.common import Month, OutputModel

Source = Literal["model", "base_model"]


class CategoryForecast(OutputModel):
    category_id: int
    name: str
    icon: str
    spent_cents: int
    p50_cents: int  # valor provável do mês
    p90_cents: int  # teto: o mês fecha abaixo dele em 90% das vezes
    baseline_cents: int  # estimativa estatística, para comparar
    source: Source
    alert: bool
    alert_reason: Literal["above", "pace"] | None


class ForecastTotal(OutputModel):
    spent_cents: int
    p50_cents: int
    p90_cents: int


class ForecastOut(OutputModel):
    month: Month
    day: int
    source: Source
    history_months: int  # meses fechados com algum gasto (o Painel só resume a previsão a partir de 3)
    total: ForecastTotal
    categories: list[CategoryForecast]


class ForecastModelOut(OutputModel):
    version: int
    trained_at: dt.datetime
    trained_until: Month
    feature_version: int
    metrics: dict[str, float]
    active: bool  # a versão que o app está usando
