from datetime import date

import pytest
from sqlalchemy import select

from financeiro.domain.banks import bank_name
from financeiro.domain.enums import Bucket, Kind, LineStatus, PaymentMethod, SkipReason
from financeiro.domain.statements import ParsedStatement, ParsedStatementLine
from financeiro.domain.statements import StatementNature as N
from financeiro.errors import AppError
from financeiro.models import InvoiceImport, InvoiceLine, Transaction
from financeiro.services.invoices.learning import ignore_line, include_line, resolve_line
from financeiro.services.invoices.posting import confirm_import, undo_import
from financeiro.services.invoices.statement_importer import import_statement
from tests.conftest import TODAY
from tests.factories import create_category, create_income_category, create_transaction

START, END = date(2026, 10, 1), date(2026, 10, 27)


def _line(position: int, description: str, cents: int, *, credit: bool = False, day: int = 5):
    nature = N.INFLOW if credit else N.OUTFLOW
    return ParsedStatementLine(
        position, date(2026, 10, day), nature, credit, description, description, cents, PaymentMethod.PIX
    )


def _import(db, user, *lines: ParsedStatementLine, start: date = START, end: date = END) -> InvoiceImport:
    statement, _ = import_statement(
        db, user.id, ParsedStatement("nubank", "ANA SOUZA", start, end, list(lines))
    )
    return statement


def _rows(db, statement: InvoiceImport) -> list[InvoiceLine]:
    db.expire_all()
    query = select(InvoiceLine).where(InvoiceLine.import_id == statement.id).order_by(InvoiceLine.position)
    return list(db.scalars(query).all())


def _rule(client, pattern: str, category_id: int) -> None:
    rule = {"pattern": pattern, "match_type": "contains", "category_id": category_id}
    assert client.post("/api/category-rules", json=rule).status_code == 201


def test_confirm_statement_creates_income_and_expense(client, db, user):
    salary = create_income_category(client)
    food = create_category(client, name="Comida fora", default_bucket="wants")
    _rule(client, "EMPRESA X", salary["id"])
    _rule(client, "PADARIA", food["id"])
    statement = _import(
        db, user, _line(1, "EMPRESA X", 150000, credit=True), _line(2, "PADARIA", 1250, day=6)
    )
    confirm_import(db, statement, today=TODAY)
    transactions = db.scalars(select(Transaction).order_by(Transaction.id)).all()
    assert [
        (tx.description, tx.kind, tx.bucket, tx.payment_method, tx.card_id, tx.amount_cents, tx.date)
        for tx in transactions
    ] == [
        ("EMPRESA X", Kind.INCOME, None, PaymentMethod.PIX, None, 150000, date(2026, 10, 5)),
        ("PADARIA", Kind.EXPENSE, Bucket.WANTS, PaymentMethod.PIX, None, 1250, date(2026, 10, 6)),
    ]
    assert {tx.notes for tx in transactions} == {"Importado do extrato Nubank (01/10/2026 a 27/10/2026)"}
    assert [row.status for row in _rows(db, statement)] == [LineStatus.IMPORTED, LineStatus.IMPORTED]


def test_bank_names_come_from_the_table():
    assert (bank_name("inter"), bank_name("nubank"), bank_name("novo")) == ("Inter", "Nubank", "novo")


def test_income_line_rejects_expense_category(client, db, user):
    food = create_category(client, name="Comida fora", default_bucket="wants")
    salary = create_income_category(client)
    statement = _import(db, user, _line(1, "FULANO", 5000, credit=True))
    [line] = _rows(db, statement)
    with pytest.raises(AppError) as error:
        resolve_line(db, line, food["id"], remember=True, today=TODAY)
    assert error.value.field == "category_id"
    db.rollback()
    resolve_line(db, line, salary["id"], remember=True, today=TODAY)
    assert (_rows(db, statement)[0].status, _rows(db, statement)[0].category_id) == (
        LineStatus.IDENTIFIED,
        salary["id"],
    )


def test_ignore_and_back_to_standby(db, user):
    statement = _import(db, user, _line(1, "CARLOS", 4000))
    [line] = _rows(db, statement)
    ignore_line(db, line)
    [ignored] = _rows(db, statement)
    assert (ignored.status, ignored.skip_reason) == (LineStatus.SKIPPED, SkipReason.IGNORED)
    include_line(db, ignored, today=TODAY)
    [back] = _rows(db, statement)
    assert (back.status, back.skip_reason) == (LineStatus.PENDING, None)


def test_ignore_imported_line_is_conflict(client, db, user):
    food = create_category(client, name="Comida fora", default_bucket="wants")
    _rule(client, "PADARIA", food["id"])
    statement = _import(db, user, _line(1, "PADARIA", 1250))
    confirm_import(db, statement, today=TODAY)
    [line] = _rows(db, statement)
    with pytest.raises(AppError) as error:
        ignore_line(db, line)
    assert error.value.status_code == 409


def test_include_refuses_other_skips(db, user):
    statement = _import(
        db, user, ParsedStatementLine(1, START, N.OWN_TRANSFER, True, "ANA", "ANA", 100, PaymentMethod.PIX)
    )
    [line] = _rows(db, statement)
    with pytest.raises(AppError) as error:
        include_line(db, line, today=TODAY)
    assert (error.value.status_code, error.value.message) == (
        409,
        "Esta linha não pode voltar para a importação.",
    )


def test_include_already_imported_line(client, db, user):
    food = create_category(client, name="Comida fora", default_bucket="wants")
    _rule(client, "PADARIA", food["id"])
    _import(db, user, _line(1, "PADARIA", 1250), end=date(2026, 10, 10))
    second = _import(db, user, _line(1, "PADARIA", 1250))
    [line] = _rows(db, second)
    assert line.skip_reason is SkipReason.ALREADY_IMPORTED
    include_line(db, line, today=TODAY)
    [included] = _rows(db, second)
    assert (included.status, included.category_id) == (LineStatus.IDENTIFIED, food["id"])


def test_learned_income_rule_does_not_touch_expense_lines(client, db, user):
    salary = create_income_category(client)
    gifts = create_category(client, name="Presentes", default_bucket="wants")
    statement = _import(
        db,
        user,
        _line(1, "MARIA", 5000, credit=True),
        _line(2, "MARIA", 3000),
        _line(3, "MARIA", 7000, credit=True, day=9),
    )
    income, expense, other_income = _rows(db, statement)
    resolve_line(db, income, salary["id"], remember=True, today=TODAY)
    assert [row.status for row in _rows(db, statement)] == [
        LineStatus.IDENTIFIED,
        LineStatus.PENDING,
        LineStatus.IDENTIFIED,
    ]
    resolve_line(db, expense, gifts["id"], remember=True, today=TODAY)
    assert [row.category_id for row in _rows(db, statement)] == [salary["id"], gifts["id"], salary["id"]]
    assert other_income.id == _rows(db, statement)[2].id


def test_undo_statement_deletes_only_its_transactions(client, db, user):
    food = create_category(client, name="Comida fora", default_bucket="wants")
    _rule(client, "PADARIA", food["id"])
    manual = create_transaction(client, food["id"], description="Feira", amount_cents=999, date="2026-10-20")
    statement = _import(db, user, _line(1, "PADARIA", 1250))
    confirm_import(db, statement, today=TODAY)
    undo_import(db, statement, today=TODAY)
    assert [tx.id for tx in db.scalars(select(Transaction)).all()] == [manual["id"]]
