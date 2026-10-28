from enum import StrEnum


class Kind(StrEnum):
    INCOME = "income"
    EXPENSE = "expense"


class Bucket(StrEnum):
    """Grupo do orçamento 50/30/20."""

    NEEDS = "needs"
    WANTS = "wants"
    SAVINGS = "savings"


class PaymentMethod(StrEnum):
    PIX = "pix"
    DEBIT = "debit"
    CASH = "cash"
    BANK_SLIP = "bank_slip"
    TRANSFER = "transfer"
    CREDIT_CARD = "credit_card"


class InvoiceStatus(StrEnum):
    FUTURE = "future"
    OPEN = "open"
    CLOSED = "closed"
    PAST = "past"


class Thermometer(StrEnum):
    NO_DATA = "no_data"
    CONTROLLED = "controlled"
    WARNING = "warning"
    NEGATIVE = "negative"
