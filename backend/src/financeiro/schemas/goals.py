import datetime as dt
from typing import Annotated

from pydantic import StringConstraints

from financeiro.schemas.common import AmountCents, Flag, Icon, InputModel, IsoDate, OutputModel


class GoalIn(InputModel):
    name: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    icon: Icon = ""
    target_cents: AmountCents
    target_date: IsoDate | None = None
    archived: Flag = False


class GoalOut(OutputModel):
    id: int
    name: str
    icon: str
    target_cents: int
    target_date: dt.date | None
    archived: bool
    saved_cents: int
    remaining_cents: int
    progress_pct: float
    months_left: int | None
    monthly_needed_cents: int | None
