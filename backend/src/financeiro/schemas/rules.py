from typing import Annotated

from pydantic import StringConstraints

from financeiro.domain.enums import Kind, MatchType, RuleSource
from financeiro.schemas.common import EntityId, InputModel, OutputModel

RulePattern = Annotated[str, StringConstraints(min_length=1, max_length=80)]


class RuleIn(InputModel):
    pattern: RulePattern
    match_type: MatchType
    category_id: EntityId


class RuleOut(OutputModel):
    id: int
    pattern: str
    match_type: MatchType
    category_id: int
    kind: Kind
    source: RuleSource
