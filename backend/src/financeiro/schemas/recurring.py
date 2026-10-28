from financeiro.domain.enums import Bucket, Kind, PaymentMethod
from financeiro.schemas.common import (
    AmountCents,
    DayOfMonth,
    Description,
    EntityId,
    InputModel,
    IsoDate,
    Month,
    Notes,
    OutputModel,
)


class RecurringIn(InputModel):
    description: Description
    kind: Kind
    amount_cents: AmountCents
    category_id: EntityId
    bucket: Bucket | None = None
    day_of_month: DayOfMonth
    payment_method: PaymentMethod
    card_id: EntityId | None = None
    start_month: Month
    end_month: Month | None = None
    notes: Notes = ""


class RecurringOut(OutputModel):
    id: int
    description: str
    kind: Kind
    amount_cents: int
    category_id: int
    bucket: Bucket | None
    day_of_month: int
    payment_method: PaymentMethod
    card_id: int | None
    start_month: Month
    end_month: Month | None
    notes: str


class ConfirmIn(InputModel):
    """Confirma a ocorrência do mês. Valor e data podem ser ajustados ao que foi pago de fato."""

    month: Month
    amount_cents: AmountCents | None = None
    date: IsoDate | None = None
