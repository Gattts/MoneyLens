"""Fatura lida de um PDF, em formato neutro (igual para qualquer banco)."""

import datetime as dt
from dataclasses import dataclass


@dataclass(frozen=True)
class ParsedLine:
    position: int  # ordem na fatura, a partir de 1
    date: dt.date
    description: str  # sem o "(Parcela k de N)"
    amount_cents: int  # sempre positivo; crédito é indicado por is_credit
    is_credit: bool
    installment_number: int | None = None
    installment_total: int | None = None


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
