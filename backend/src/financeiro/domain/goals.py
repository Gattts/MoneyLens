"""Progresso de uma meta de poupança."""

from dataclasses import dataclass
from datetime import date

from financeiro.domain.months import months_between


@dataclass(frozen=True)
class GoalProgress:
    remaining_cents: int
    progress_pct: float
    months_left: int | None
    monthly_needed_cents: int | None


def goal_progress(target_cents: int, saved_cents: int, target_date: date | None, today: date) -> GoalProgress:
    """Quanto falta e quanto guardar por mês, contando o mês atual até o mês da data-alvo."""
    remaining = max(0, target_cents - saved_cents)
    progress_pct = round(saved_cents * 100 / target_cents, 1)
    if target_date is None:
        return GoalProgress(remaining, progress_pct, None, None)
    months_left = max(0, months_between(today, target_date) + 1)
    if remaining == 0:
        monthly = 0
    elif months_left == 0:
        monthly = remaining
    else:
        monthly = -(-remaining // months_left)  # divisão arredondando para cima
    return GoalProgress(remaining, progress_pct, months_left, monthly)
