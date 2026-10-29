"""Escolha da regra de categoria para um estabelecimento."""

from collections.abc import Sequence
from dataclasses import dataclass

from financeiro.domain.enums import Kind, MatchType


@dataclass(frozen=True)
class RuleView:
    id: int
    pattern: str
    match_type: MatchType
    category_id: int
    kind: Kind  # o da categoria: entradas só casam com regras de receita


def find_rule(key: str, rules: Sequence[RuleView], kind: Kind) -> RuleView | None:
    """Só regras do tipo da linha. Exata primeiro; depois a de "contém" com o padrão mais longo.

    No empate vence a mais antiga. "Contém" ignora espaços: "99FOOD" casa com "99 FOOD" (como vem no Pix).
    """
    same_kind = [rule for rule in rules if rule.kind is kind]
    exact = [rule for rule in same_kind if rule.match_type is MatchType.EXACT and rule.pattern == key]
    if exact:
        return min(exact, key=lambda rule: rule.id)
    compact = key.replace(" ", "")
    contains = [
        rule
        for rule in same_kind
        if rule.match_type is MatchType.CONTAINS and rule.pattern.replace(" ", "") in compact
    ]
    return min(contains, key=lambda rule: (-len(rule.pattern), rule.id), default=None)
