from financeiro.schemas.common import InputModel, OutputModel, Percent


class BudgetSettingsIn(InputModel):
    needs_pct: Percent
    wants_pct: Percent
    savings_pct: Percent


class BudgetSettingsOut(OutputModel):
    needs_pct: int
    wants_pct: int
    savings_pct: int
