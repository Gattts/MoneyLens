from datetime import date

from financeiro.domain.enums import MatchType, SkipReason
from financeiro.domain.invoices import ParsedLine, credit_reasons
from financeiro.domain.merchants import merchant_key
from financeiro.domain.rules import RuleView, find_rule

PAYMENT, REFUND, CREDIT = SkipReason.PAYMENT, SkipReason.REFUND, SkipReason.CREDIT


def _line(position: int, description: str, cents: int, *, credit: bool = False) -> ParsedLine:
    return ParsedLine(position, date(2026, 9, 1), description, cents, credit)


def test_merchant_key_normalizes():
    assert merchant_key("  Café da  Esquina (Parcela 02 de 10) ") == "CAFE DA ESQUINA"
    assert merchant_key("IFD*Drogaria São João") == "IFD*DROGARIA SAO JOAO"
    assert merchant_key("APPLE.COM/BILL") == "APPLE.COM/BILL"


def test_exact_rule_beats_contains():
    rules = [RuleView(1, "UBER", MatchType.CONTAINS, 10), RuleView(2, "UBER *TRIP", MatchType.EXACT, 20)]
    assert find_rule("UBER *TRIP", rules) == rules[1]


def test_longest_contains_wins():
    rules = [RuleView(1, "UBER", MatchType.CONTAINS, 10), RuleView(2, "UBER EATS", MatchType.CONTAINS, 30)]
    assert find_rule("UBER EATS *PEDIDO", rules) == rules[1]


def test_contains_tie_goes_to_lowest_id():
    rules = [RuleView(7, "LOJA", MatchType.CONTAINS, 10), RuleView(3, "CASA", MatchType.CONTAINS, 30)]
    assert find_rule("CASA LOJA", rules) == rules[1]


def test_exact_rule_needs_the_whole_name():
    assert find_rule("UBER *TRIP HELP", [RuleView(1, "UBER *TRIP", MatchType.EXACT, 20)]) is None


def test_no_rule_returns_none():
    assert find_rule("PADARIA", [RuleView(1, "UBER", MatchType.CONTAINS, 10)]) is None


def test_payment_refund_and_unmatched_credit():
    lines = [
        _line(1, "Loja Boa", 4770),
        _line(2, "LOJA BOA", 4770, credit=True),
        _line(3, "PAGAMENTO ON LINE", 10000, credit=True),
        _line(4, "OUTRA", 500, credit=True),
    ]
    assert credit_reasons(lines) == {1: REFUND, 2: REFUND, 3: PAYMENT, 4: CREDIT}


def test_partial_refund_does_not_cancel_purchase():
    lines = [_line(1, "LOJA", 4770), _line(2, "LOJA", 2000, credit=True)]
    assert credit_reasons(lines) == {2: CREDIT}


def test_one_debit_cancels_only_one_credit():
    lines = [_line(1, "LOJA", 4770), _line(2, "LOJA", 4770, credit=True), _line(3, "LOJA", 4770, credit=True)]
    assert credit_reasons(lines) == {1: REFUND, 2: REFUND, 3: CREDIT}


def test_debits_without_credits_are_not_classified():
    assert credit_reasons([_line(1, "LOJA", 100), _line(2, "OUTRA", 200)]) == {}
