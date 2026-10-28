"""Tipos compartilhados: limites de valores, datas e meses."""

import re
from datetime import date
from typing import Annotated, Any

from fastapi import Path
from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    PlainSerializer,
    StrictBool,
    StrictInt,
    StringConstraints,
)
from pydantic_core import PydanticCustomError

from financeiro.domain.months import format_month

MAX_AMOUNT_CENTS = 100_000_000_000  # R$ 1 bilhão
MAX_ID = 2**63 - 1  # maior inteiro do SQLite
MIN_DATE = date(2000, 1, 1)
MAX_DATE = date(2100, 12, 31)
MONTHS_IN_YEAR = 12


class InputModel(BaseModel):
    """Corpo de requisição: campos desconhecidos são rejeitados e textos chegam sem espaços nas pontas."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OutputModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _parse_month(value: Any) -> date:
    if isinstance(value, date):
        return value.replace(day=1)
    if isinstance(value, str):
        match = re.fullmatch(r"(\d{4})-(\d{2})", value.strip())
        if match:
            year, month = int(match[1]), int(match[2])
            if 1 <= month <= MONTHS_IN_YEAR and MIN_DATE.year <= year <= MAX_DATE.year:
                return date(year, month, 1)
    raise PydanticCustomError("month_format", "Mês inválido. Use o formato AAAA-MM, entre 2000 e 2100.")


def _require_date_text(value: Any) -> Any:
    # Sem isto, o Pydantic aceitaria números como timestamp Unix (ex.: 1767225600 viraria 2026-01-01).
    if isinstance(value, str | date):
        return value
    raise PydanticCustomError("date_type", "Data inválida. Use o formato AAAA-MM-DD.")


def _check_date_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise PydanticCustomError("date_range", "Use uma data entre 01/01/2000 e 31/12/2100.")
    return value


Name = Annotated[str, StringConstraints(min_length=1, max_length=60)]
Description = Annotated[str, StringConstraints(min_length=1, max_length=120)]
Notes = Annotated[str, StringConstraints(max_length=500)]
Icon = Annotated[str, StringConstraints(max_length=16)]
AmountCents = Annotated[StrictInt, Field(gt=0, le=MAX_AMOUNT_CENTS)]
LimitCents = Annotated[StrictInt, Field(ge=0, le=MAX_AMOUNT_CENTS)]
DayOfMonth = Annotated[StrictInt, Field(ge=1, le=31)]
Percent = Annotated[StrictInt, Field(ge=0, le=100)]
EntityId = Annotated[StrictInt, Field(gt=0, le=MAX_ID)]
Flag = StrictBool
IsoDate = Annotated[date, BeforeValidator(_require_date_text), AfterValidator(_check_date_range)]
# Só vira texto "AAAA-MM" na resposta JSON; em model_dump() continua `date`, como o banco espera.
Month = Annotated[
    date,
    BeforeValidator(_parse_month),
    PlainSerializer(format_month, return_type=str, when_used="json"),
]
ItemId = Annotated[int, Path(gt=0, le=MAX_ID)]
