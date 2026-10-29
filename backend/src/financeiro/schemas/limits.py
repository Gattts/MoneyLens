"""Tetos de gasto por categoria, a sugestão de valor e os alertas."""

import datetime as dt
from typing import Annotated

from pydantic import Field

from financeiro.domain.enums import LimitAlertKind
from financeiro.schemas.common import AmountCents, EntityId, InputModel, Month, OutputModel

MAX_READ_IDS = 100


class LimitIn(InputModel):
    category_id: EntityId
    amount_cents: AmountCents


class LimitUpdate(InputModel):
    """Só o valor muda; para trocar a categoria, apague e crie outro teto."""

    amount_cents: AmountCents


class LimitOut(OutputModel):
    id: int
    category_id: int
    name: str
    icon: str
    amount_cents: int
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
