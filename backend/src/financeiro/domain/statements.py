"""Extrato de conta lido de um PDF, em formato neutro (igual para qualquer banco)."""

import datetime as dt
from dataclasses import dataclass
from enum import StrEnum

from financeiro.domain.enums import PaymentMethod


class StatementNature(StrEnum):
    """O que a movimentação é, decidido pelo leitor do banco."""

    OUTFLOW = "outflow"  # saída comum: Pix enviado, compra no débito
    INFLOW = "inflow"  # entrada comum: Pix ou transferência recebida
    INVESTMENT = "investment"  # aplicação ou resgate
    CARD_PAYMENT = "card_payment"  # pagamento da fatura do cartão
    OWN_TRANSFER = "own_transfer"  # de ou para o próprio titular


@dataclass(frozen=True)
class ParsedStatementLine:
    position: int  # ordem no extrato, a partir de 1
    date: dt.date
    nature: StatementNature
    is_credit: bool  # dinheiro que entrou na conta
    counterparty: str  # nome, sem CPF/CNPJ, banco, agência e conta ("" quando não há)
    description: str  # o que vira o nome do lançamento e a chave das regras
    amount_cents: int  # sempre positivo; o sentido é is_credit
    payment_method: PaymentMethod


@dataclass(frozen=True)
class ParsedStatement:
    bank: str
    holder: str
    period_start: dt.date
    period_end: dt.date
    lines: list[ParsedStatementLine]
