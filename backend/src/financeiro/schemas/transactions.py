import datetime as dt
from typing import Annotated

from pydantic import Field, StrictInt

from financeiro.domain.enums import Bucket, Kind, PaymentMethod
from financeiro.schemas.common import (
    AmountCents,
    Description,
    EntityId,
    InputModel,
    IsoDate,
    Month,
    Notes,
    OutputModel,
)

MAX_INSTALLMENTS = 48


class TransactionIn(InputModel):
    description: Description
    kind: Kind
    amount_cents: AmountCents
    date: IsoDate
    category_id: EntityId
    bucket: Bucket | None = None
    payment_method: PaymentMethod
    card_id: EntityId | None = None
    goal_id: EntityId | None = None
    notes: Notes = ""


class TransactionCreate(TransactionIn):
    """Na criação, `amount_cents` é o valor total da compra; com parcelas, ele é dividido."""

    installments: Annotated[StrictInt, Field(ge=1, le=MAX_INSTALLMENTS)] = 1


class TransactionOut(OutputModel):
    id: int
    description: str
    kind: Kind
    amount_cents: int
    date: dt.date
    category_id: int
    bucket: Bucket | None
    payment_method: PaymentMethod
    card_id: int | None
    goal_id: int | None
    notes: str
    installment_group: str | None
    installment_number: int | None
    installment_total: int | None
    recurring_rule_id: int | None
    recurrence_month: Month | None
    payment_month: Month  # no cartão, o mês em que a fatura vence
