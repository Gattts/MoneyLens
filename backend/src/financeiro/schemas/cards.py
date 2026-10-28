import datetime as dt

from financeiro.domain.enums import InvoiceStatus
from financeiro.schemas.common import DayOfMonth, Flag, InputModel, LimitCents, Month, Name, OutputModel
from financeiro.schemas.transactions import TransactionOut


class CardIn(InputModel):
    name: Name
    limit_cents: LimitCents
    closing_day: DayOfMonth
    due_day: DayOfMonth
    archived: Flag = False


class InvoiceSummary(OutputModel):
    month: Month
    closing_date: dt.date
    due_date: dt.date
    total_cents: int
    status: InvoiceStatus


class CardOut(OutputModel):
    id: int
    name: str
    limit_cents: int
    closing_day: int
    due_day: int
    archived: bool
    has_invoice_password: bool
    used_cents: int
    available_cents: int
    current_invoice: InvoiceSummary


class InvoiceOut(InvoiceSummary):
    card_id: int
    period_start: dt.date
    period_end: dt.date
    transactions: list[TransactionOut]
