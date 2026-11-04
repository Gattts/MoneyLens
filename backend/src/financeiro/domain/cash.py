"""Mês de pagamento: o mês em que o dinheiro sai da conta.

Compra no cartão conta no mês em que vence a fatura dela; receitas e o que não é cartão, no mês da data.
"""

from datetime import date
from typing import NamedTuple

from financeiro.domain.cards import due_date, invoice_month_for
from financeiro.domain.enums import Kind, PaymentMethod
from financeiro.domain.months import add_months, first_day


class CardCycle(NamedTuple):
    closing_day: int
    due_day: int


def payment_month(day: date, kind: Kind, method: PaymentMethod, cycle: CardCycle | None) -> date:
    if kind is not Kind.EXPENSE or method is not PaymentMethod.CREDIT_CARD or cycle is None:
        return first_day(day)
    invoice_month = invoice_month_for(day, cycle.closing_day)
    return first_day(due_date(invoice_month, cycle.closing_day, cycle.due_day))


def due_invoice_month(month: date, cycle: CardCycle) -> date:
    """A fatura (pelo mês em que fecha) que vence em `month`."""
    return first_day(month) if cycle.due_day > cycle.closing_day else add_months(first_day(month), -1)


def split_paid(amounts: list[int], paid_cents: int, total_cents: int) -> list[tuple[int, int]]:
    """(realizado, previsto) de cada compra de uma fatura, pela parte já paga dela.

    A divisão é proporcional e não perde centavo: o resto do arredondamento fica no previsto.
    Fatura sem total ou paga por inteiro (ou a mais) conta tudo como realizado.
    """
    if total_cents <= 0 or paid_cents >= total_cents:
        return [(amount, 0) for amount in amounts]
    remaining = max(0, paid_cents)
    split = []
    for amount in amounts:
        realized = min(amount, remaining, amount * max(0, paid_cents) // total_cents)
        remaining -= realized
        split.append((realized, amount - realized))
    # Os arredondamentos para baixo deixam alguns centavos pagos sem dono: vão para as primeiras compras.
    for index, (realized, pending) in enumerate(split):
        if remaining == 0:
            break
        extra = min(pending, remaining)
        split[index] = (realized + extra, pending - extra)
        remaining -= extra
    return split
