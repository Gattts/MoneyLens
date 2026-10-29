"""Históricos inventados para pré-treinar o modelo base. Nenhum dado aqui é real.

Cada categoria segue um padrão típico: conta fixa, mercado semanal, lazer aleatório ou compra grande
ocasional.
"""

import calendar
import random
from datetime import date

from financeiro.domain.months import add_months
from financeiro.forecast.history import Expense

START = date(2025, 1, 1)
PATTERNS = ("fixed", "weekly", "leisure", "occasional")
BIG_PURCHASE_CHANCE = 0.3


def synthetic_history(seed: int, months: int, categories: int) -> list[Expense]:
    rng = random.Random(seed)  # noqa: S311  # nosec B311 - dados de treino inventados, não é segurança
    expenses: list[Expense] = []
    for category_id in range(1, categories + 1):
        pattern = PATTERNS[(category_id - 1) % len(PATTERNS)]
        level = rng.randint(5_000, 200_000)  # gasto típico do mês nessa categoria, em centavos
        bill_day = rng.randint(1, 28)
        for index in range(months):
            month = add_months(START, index)
            expenses += _month(rng, pattern, category_id, month, level=level, bill_day=bill_day)
    return expenses


def _month(
    rng: random.Random, pattern: str, category_id: int, month: date, *, level: int, bill_day: int
) -> list[Expense]:
    length = calendar.monthrange(month.year, month.month)[1]

    def on(day: int, cents: float, fixed: bool = False) -> Expense:
        return Expense(
            date(month.year, month.month, min(day, length)), category_id, max(100, round(cents)), fixed
        )

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
