import datetime as dt

from pydantic import computed_field

from financeiro.domain.enums import ImportSource, Kind, LineStatus, PaymentMethod, SkipReason
from financeiro.domain.invoices import kind_of
from financeiro.schemas.common import EntityId, Flag, InputModel, Month, OutputModel


class PaymentSuggestionOut(OutputModel):
    card_id: int
    card_name: str
    invoice_month: Month
    due_date: dt.date


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
    payment_method: PaymentMethod | None
    status: LineStatus
    skip_reason: SkipReason | None
    category_id: int | None
    rule_id: int | None
    transaction_id: int | None
    duplicate_of: str | None = None  # nome da fixa prevista que esta linha parece ser
    payment_id: int | None = None  # pagamento de fatura registrado a partir desta linha
    # A única fatura que esta linha do extrato pode pagar (valor exato e perto do vencimento).
    payment_suggestion: PaymentSuggestionOut | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def kind(self) -> Kind:
        return kind_of(self.is_credit)


class InvoiceImportOut(OutputModel):
    id: int
    source: ImportSource
    card_id: int | None
    bank: str
    due_date: dt.date | None
    period_start: dt.date | None
    period_end: dt.date | None
    total_cents: int
    confirmed_at: dt.datetime | None
    created_at: dt.datetime
    line_count: int
    pending_count: int
    pending_cents: int


class InvestmentOut(OutputModel):
    applied_cents: int
    redeemed_cents: int


class InvoiceImportDetailOut(InvoiceImportOut):
    lines: list[InvoiceLineOut]
    investment: InvestmentOut | None = None  # só no extrato: aplicações e resgates novos
    already_imported: bool = False


class InvoiceImportListOut(OutputModel):
    imports: list[InvoiceImportOut]
    standby_count: int
    standby_cents: int


class LinePaymentIn(InputModel):
    card_id: EntityId
    invoice_month: Month


class LineUpdateIn(InputModel):
    category_id: EntityId
    remember: Flag = True
