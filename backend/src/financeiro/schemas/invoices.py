import datetime as dt

from financeiro.domain.enums import LineStatus, SkipReason
from financeiro.schemas.common import EntityId, Flag, InputModel, OutputModel


class InvoiceLineOut(OutputModel):
    id: int
    position: int
    date: dt.date
    description: str
    merchant_key: str
    amount_cents: int
    is_credit: bool
    installment_number: int | None
    installment_total: int | None
    status: LineStatus
    skip_reason: SkipReason | None
    category_id: int | None
    rule_id: int | None
    transaction_id: int | None


class InvoiceImportOut(OutputModel):
    id: int
    card_id: int
    bank: str
    due_date: dt.date
    total_cents: int
    confirmed_at: dt.datetime | None
    created_at: dt.datetime
    line_count: int
    pending_count: int
    pending_cents: int


class InvoiceImportDetailOut(InvoiceImportOut):
    lines: list[InvoiceLineOut]
    already_imported: bool = False


class InvoiceImportListOut(OutputModel):
    imports: list[InvoiceImportOut]
    standby_count: int
    standby_cents: int


class LineUpdateIn(InputModel):
    category_id: EntityId
    remember: Flag = True
