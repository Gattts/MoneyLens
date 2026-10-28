"""Escolha da regra de categoria para um estabelecimento."""

from collections.abc import Sequence
from dataclasses import dataclass

from financeiro.domain.enums import MatchType


@dataclass(frozen=True)
class RuleView:
    id: int
    pattern: str
    match_type: MatchType
    category_id: int


def find_rule(key: str, rules: Sequence[RuleView]) -> RuleView | None:
    """Regra exata primeiro; depois a de "contém" com o padrão mais longo (empate: a mais antiga)."""
    exact = [rule for rule in rules if rule.match_type is MatchType.EXACT and rule.pattern == key]
    if exact:
        return min(exact, key=lambda rule: rule.id)
    contains = [rule for rule in rules if rule.match_type is MatchType.CONTAINS and rule.pattern in key]
    return min(contains, key=lambda rule: (-len(rule.pattern), rule.id), default=None)
