"""Tetos de gasto por categoria, a sugestão de valor e os alertas."""

import datetime as dt
from typing import Annotated, Self

from pydantic import Field, StrictInt, model_validator
from pydantic_core import PydanticCustomError

from financeiro.domain.enums import LimitAlertKind
from financeiro.schemas.common import AmountCents, EntityId, InputModel, Month, OutputModel

MAX_READ_IDS = 100
ONE_OF = "Informe o valor ou a porcentagem da renda."
IncomePercent = Annotated[StrictInt, Field(ge=1, le=100)]


class LimitValue(InputModel):
    """O teto é um valor fixo ou uma porcentagem da renda prevista do mês (um dos dois)."""

    amount_cents: AmountCents | None = None
    income_percent: IncomePercent | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.amount_cents is None) == (self.income_percent is None):
            raise PydanticCustomError("amount_or_income_percent", ONE_OF)
        return self


class LimitIn(LimitValue):
    category_id: EntityId


class LimitUpdate(LimitValue):
    """Muda o valor ou a forma (R$ ou %); para trocar a categoria, apague e crie outro teto."""


class LimitOut(OutputModel):
    id: int
    category_id: int
    name: str
    icon: str
    amount_cents: int  # o teto em reais neste mês (no teto por %, calculado da renda prevista)
    income_percent: int | None  # preenchido no teto por % da renda
    income_cents: int | None  # a renda prevista usada (só no teto por %)
    no_income: bool  # teto por % num mês sem renda prevista: fica inativo
    spent_cents: int  # do dia 1 até hoje
    percent: int  # arredondado para baixo
    p50_cents: int | None  # valor provável do mês pela previsão; nulo se a categoria não está nela
    will_exceed: bool  # "vai estourar": a partir do dia 7
    active: bool  # categoria de despesa e não arquivada


class SuggestionOut(OutputModel):
    suggested_cents: int | None  # nulo: categoria sem histórico
    low_cents: int
    high_cents: int
    months: int
    income_cents: int  # renda prevista do mês
    suggested_percent: int | None  # a sugestão em % da renda, arredondada para cima


class AlertOut(OutputModel):
    id: int
    kind: LimitAlertKind
    category_id: int
    name: str
    icon: str
    spent_cents: int
    limit_cents: int
    forecast_cents: int | None
    month: Month
    created_at: dt.datetime
    read_at: dt.datetime | None


class AlertsOut(OutputModel):
    unread: int
    items: list[AlertOut]  # os mais recentes, sem os silenciosos


class AlertsReadIn(InputModel):
    ids: Annotated[list[EntityId], Field(max_length=MAX_READ_IDS)] | None = None  # sem ids: todos
