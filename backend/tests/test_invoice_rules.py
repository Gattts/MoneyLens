from datetime import date

from financeiro.domain.enums import Kind, MatchType, SkipReason
from financeiro.domain.invoices import ParsedLine, credit_reasons
from financeiro.domain.merchants import merchant_key
from financeiro.domain.rules import RuleView, find_rule

PAYMENT, REFUND, CREDIT = SkipReason.PAYMENT, SkipReason.REFUND, SkipReason.CREDIT


def _line(
    position: int, description: str, cents: int, *, credit: bool = False, payment: bool = False
) -> ParsedLine:
    return ParsedLine(position, date(2026, 9, 1), description, cents, credit, is_payment=payment)


def test_merchant_key_normalizes():
    assert merchant_key("  Café da  Esquina (Parcela 02 de 10) ") == "CAFE DA ESQUINA"
    assert merchant_key("IFD*Drogaria São João") == "IFD*DROGARIA SAO JOAO"
    assert merchant_key("APPLE.COM/BILL") == "APPLE.COM/BILL"


def test_exact_rule_beats_contains():
    rules = [
        RuleView(1, "UBER", MatchType.CONTAINS, 10, Kind.EXPENSE),
        RuleView(2, "UBER *TRIP", MatchType.EXACT, 20, Kind.EXPENSE),
    ]
    assert find_rule("UBER *TRIP", rules, Kind.EXPENSE) == rules[1]


def test_longest_contains_wins():
    rules = [
        RuleView(1, "UBER", MatchType.CONTAINS, 10, Kind.EXPENSE),
        RuleView(2, "UBER EATS", MatchType.CONTAINS, 30, Kind.EXPENSE),
    ]
    assert find_rule("UBER EATS *PEDIDO", rules, Kind.EXPENSE) == rules[1]


def test_contains_tie_goes_to_lowest_id():
    rules = [
        RuleView(7, "LOJA", MatchType.CONTAINS, 10, Kind.EXPENSE),
        RuleView(3, "CASA", MatchType.CONTAINS, 30, Kind.EXPENSE),
    ]
    assert find_rule("CASA LOJA", rules, Kind.EXPENSE) == rules[1]


def test_exact_rule_needs_the_whole_name():
    assert (
        find_rule(
            "UBER *TRIP HELP", [RuleView(1, "UBER *TRIP", MatchType.EXACT, 20, Kind.EXPENSE)], Kind.EXPENSE
        )
        is None
    )


def test_contains_ignores_spaces():
    rules = [RuleView(1, "99FOOD", MatchType.CONTAINS, 10, Kind.EXPENSE)]
    assert find_rule("99 FOOD", rules, Kind.EXPENSE) == rules[0]
    taxi = [RuleView(2, "99 TAXI", MatchType.CONTAINS, 11, Kind.EXPENSE)]
    assert find_rule("99TAXI SP", taxi, Kind.EXPENSE) == taxi[0]
    assert find_rule("99FOOD", taxi, Kind.EXPENSE) is None


def test_rule_of_other_kind_is_ignored():
    rules = [
        RuleView(1, "MARIA", MatchType.EXACT, 10, Kind.EXPENSE),
        RuleView(2, "MARIA", MatchType.EXACT, 20, Kind.INCOME),
    ]
    assert find_rule("MARIA", rules, Kind.INCOME) == rules[1]
    assert find_rule("MARIA", rules, Kind.EXPENSE) == rules[0]
    assert find_rule("MARIA", rules[:1], Kind.INCOME) is None


def test_no_rule_returns_none():
    assert (
        find_rule("PADARIA", [RuleView(1, "UBER", MatchType.CONTAINS, 10, Kind.EXPENSE)], Kind.EXPENSE)
        is None
    )


def test_payment_refund_and_unmatched_credit():
    lines = [
        _line(1, "Loja Boa", 4770),
        _line(2, "LOJA BOA", 4770, credit=True),
        _line(3, "PAGAMENTO ON LINE", 10000, credit=True, payment=True),
        _line(4, "OUTRA", 500, credit=True),
    ]
    assert credit_reasons(lines) == {1: REFUND, 2: REFUND, 3: PAYMENT, 4: CREDIT}


def test_payment_comes_from_the_reader_not_from_the_name():
    lines = [_line(1, "PAGAMENTO EXTRA", 500, credit=True), _line(2, "PIX", 900, credit=True, payment=True)]
    assert credit_reasons(lines) == {1: CREDIT, 2: PAYMENT}


def test_partial_refund_does_not_cancel_purchase():
    lines = [_line(1, "LOJA", 4770), _line(2, "LOJA", 2000, credit=True)]
    assert credit_reasons(lines) == {2: CREDIT}


def test_one_debit_cancels_only_one_credit():
    lines = [_line(1, "LOJA", 4770), _line(2, "LOJA", 4770, credit=True), _line(3, "LOJA", 4770, credit=True)]
    assert credit_reasons(lines) == {1: REFUND, 2: REFUND, 3: CREDIT}


def test_debits_without_credits_are_not_classified():
    assert credit_reasons([_line(1, "LOJA", 100), _line(2, "OUTRA", 200)]) == {}
