"""Históricos inventados para pré-treinar o modelo base. Nenhum dado aqui é real.

Cada categoria segue um padrão típico: conta fixa, mercado semanal, lazer aleatório ou compra grande
ocasional. Parte das compras vai para um cartão inventado e é paga no mês em que a fatura vence; algumas
compras grandes são parceladas.
"""

import calendar
import random
from datetime import date

from financeiro.domain.cash import CardCycle, payment_month
from financeiro.domain.enums import Kind, PaymentMethod
from financeiro.domain.months import add_months, first_day
from financeiro.forecast.history import Expense

START = date(2025, 1, 1)
PATTERNS = ("fixed", "weekly", "leisure", "occasional")
BIG_PURCHASE_CHANCE = 0.3
CARD_SHARES = (0.0, 0.5, 0.9)  # parte das compras avulsas da categoria feita no cartão
INSTALLMENTS = 3
INSTALLMENT_FROM_CENTS = 50_000  # compra a partir de R$ 500 no cartão pode ser parcelada
INSTALLMENT_CHANCE = 0.5


def synthetic_history(seed: int, months: int, categories: int) -> list[Expense]:
    rng = random.Random(seed)  # noqa: S311  # nosec B311 - dados de treino inventados, não é segurança
    expenses: list[Expense] = []
    for category_id in range(1, categories + 1):
        pattern = PATTERNS[(category_id - 1) % len(PATTERNS)]
        level = rng.randint(5_000, 200_000)  # gasto típico do mês nessa categoria, em centavos
        bill_day = rng.randint(1, 28)
        card = CardCycle(rng.randint(1, 28), rng.randint(1, 28))
        share = rng.choice(CARD_SHARES)
        for index in range(months):
            month = add_months(START, index)
            for spent in _month(rng, pattern, category_id, month, level=level, bill_day=bill_day):
                expenses += _paid(rng, spent, card, share)
    # O histórico termina no último mês gerado: o que só seria pago depois dele fica de fora.
    end = add_months(START, months)
    return [expense for expense in expenses if expense.month < end]


def _paid(rng: random.Random, spent: Expense, card: CardCycle, share: float) -> list[Expense]:
    """Leva a compra para o mês de pagamento (no cartão, o da fatura); compra grande pode ser parcelada."""
    if spent.scheduled or rng.random() >= share:
        return [spent]
    if spent.amount_cents >= INSTALLMENT_FROM_CENTS and rng.random() < INSTALLMENT_CHANCE:
        part = spent.amount_cents // INSTALLMENTS
        days = [
            add_months(first_day(spent.date), index).replace(day=min(spent.date.day, 28))
            for index in range(INSTALLMENTS)
        ]
        return [
            Expense(
                day,
                payment_month(day, Kind.EXPENSE, PaymentMethod.CREDIT_CARD, card),
                spent.category_id,
                part,
                True,
            )
            for day in days
        ]
    month = payment_month(spent.date, Kind.EXPENSE, PaymentMethod.CREDIT_CARD, card)
    return [Expense(spent.date, month, spent.category_id, spent.amount_cents, False)]


def _month(
    rng: random.Random, pattern: str, category_id: int, month: date, *, level: int, bill_day: int
) -> list[Expense]:
    length = calendar.monthrange(month.year, month.month)[1]

    def on(day: int, cents: float, fixed: bool = False) -> Expense:
        when = date(month.year, month.month, min(day, length))
        return Expense(when, month, category_id, max(100, round(cents)), fixed)

    if pattern == "fixed":
        return [on(bill_day, level * rng.uniform(0.98, 1.02), fixed=True)]
    if pattern == "weekly":
        return [on(day, level / 4 * rng.uniform(0.6, 1.4)) for day in range(rng.randint(1, 7), length + 1, 7)]
    if pattern == "leisure":
        count = rng.randint(0, 6)
        return [on(rng.randint(1, length), level / 3 * rng.lognormvariate(0, 0.6)) for _ in range(count)]
    small = [on(rng.randint(1, length), level / 10 * rng.uniform(0.5, 1.5)) for _ in range(rng.randint(0, 3))]
    big = (
        [on(rng.randint(1, length), level * rng.uniform(1.5, 3.0))]
        if rng.random() < BIG_PURCHASE_CHANCE
        else []
    )
    return small + big
