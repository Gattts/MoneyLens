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
    CLOSED = "closed"  # fechou, não venceu, sem pagamento
    PAID = "paid"
    PARTIALLY_PAID = "partially_paid"
    OVERDUE = "overdue"  # venceu sem pagamento
    PAID_BEFORE_TRACKING = "paid_before_tracking"  # venceu antes de o cartão registrar pagamentos


class Thermometer(StrEnum):
    NO_DATA = "no_data"
    CONTROLLED = "controlled"
    WARNING = "warning"
    NEGATIVE = "negative"


class MatchType(StrEnum):
    """Como uma regra compara o nome do estabelecimento."""

    EXACT = "exact"
    CONTAINS = "contains"


class RuleSource(StrEnum):
    DEFAULT = "default"  # dicionário inicial
    LEARNED = "learned"  # criada pelo usuário ou aprendida ao resolver o standby


class LineStatus(StrEnum):
    """Situação de uma linha de fatura importada."""

    IDENTIFIED = "identified"  # tem categoria, ainda não virou lançamento
    PENDING = "pending"  # em standby
    IMPORTED = "imported"
    SKIPPED = "skipped"


class SkipReason(StrEnum):
    PAYMENT = "payment"
    REFUND = "refund"
    CREDIT = "credit"
    DUPLICATE = "duplicate"
    EXISTING_INSTALLMENT = "existing_installment"
    CARD_PAYMENT = "card_payment"  # pagamento da fatura do cartão visto no extrato
    OWN_TRANSFER = "own_transfer"  # entre contas do próprio titular
    INVESTMENT = "investment"  # aplicação/resgate: entram pelo líquido do período
    ALREADY_IMPORTED = "already_imported"  # veio em outro extrato do mesmo banco
    IGNORED = "ignored"  # a pessoa escolheu não lançar


class PaymentSource(StrEnum):
    """De onde veio o registro do pagamento de uma fatura."""

    MANUAL = "manual"
    CARD_INVOICE = "card_invoice"  # crédito "PAGAMENTO" na fatura seguinte
    ACCOUNT_STATEMENT = "account_statement"  # linha do extrato confirmada pela pessoa


class ImportSource(StrEnum):
    """De onde veio a importação."""

    CARD_INVOICE = "card_invoice"
    ACCOUNT_STATEMENT = "account_statement"


class LimitAlertKind(StrEnum):
    """Alerta de um teto de gasto: um marco atingido ou o aviso de que o mês vai passar do teto."""

    REACHED_50 = "reached_50"
    REACHED_90 = "reached_90"
    REACHED_100 = "reached_100"
    FORECAST = "forecast"
