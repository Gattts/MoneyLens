"""Fatura lida de um PDF, em formato neutro (igual para qualquer banco)."""

import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass

from financeiro.domain.enums import Kind, SkipReason
from financeiro.domain.merchants import merchant_key


def kind_of(is_credit: bool) -> Kind:
    """Dinheiro que entra é receita; o que sai é despesa (compra no cartão é sempre saída)."""
    return Kind.INCOME if is_credit else Kind.EXPENSE


@dataclass(frozen=True)
class ParsedLine:
    position: int  # ordem na fatura, a partir de 1
    date: dt.date
    description: str  # sem o "(Parcela k de N)"
    amount_cents: int  # sempre positivo; crédito é indicado por is_credit
    is_credit: bool
    installment_number: int | None = None
    installment_total: int | None = None
    is_payment: bool = False  # pagamento da própria fatura, reconhecido pelo leitor do banco


@dataclass(frozen=True)
class CardSection:
    final: str  # últimos 4 dígitos do cartão
    total_cents: int
    lines: list[ParsedLine]


@dataclass(frozen=True)
class ParsedInvoice:
    bank: str
    due_date: dt.date
    cards: list[CardSection]

    @property
    def lines(self) -> list[ParsedLine]:
        return sorted((line for card in self.cards for line in card.lines), key=lambda line: line.position)


def credit_reasons(lines: Sequence[ParsedLine]) -> dict[int, SkipReason]:
    """Por posição, as linhas que ficam fora da importação por causa de créditos.

    Pagamento da fatura (marcado pelo leitor) fica fora. Um estorno anula um débito do mesmo estabelecimento
    e valor (os dois ficam fora; cada débito anula um crédito só). Um crédito sem par fica fora com aviso para
    lançar à mão.
    """
    reasons: dict[int, SkipReason] = {}
    debits = [line for line in lines if not line.is_credit]
    for credit in (line for line in lines if line.is_credit):
        if credit.is_payment:
            reasons[credit.position] = SkipReason.PAYMENT
            continue
        key = merchant_key(credit.description)
        match = next(
            (
                debit
                for debit in debits
                if debit.position not in reasons
                and debit.amount_cents == credit.amount_cents
                and merchant_key(debit.description) == key
            ),
            None,
        )
        if match is None:
            reasons[credit.position] = SkipReason.CREDIT
        else:
            reasons[match.position] = reasons[credit.position] = SkipReason.REFUND
    return reasons
