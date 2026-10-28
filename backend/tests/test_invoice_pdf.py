import pytest

from financeiro.errors import AppError
from financeiro.services.invoices.pdf import read_pdf_text
from tests.invoice_samples import inter_pdf, inter_text, row

SAMPLE = inter_text([("1111****2222", [row("23 de ago. 2026", "LOJA X", "R$ 46,00")], "R$ 46,00")])
LOCKED = inter_pdf(SAMPLE, password="4321")


def _error(data: bytes, **passwords: str | None) -> tuple[str | None, str]:
    with pytest.raises(AppError) as error:
        read_pdf_text(
            data, password=passwords.get("password"), saved_password=passwords.get("saved_password")
        )
    return error.value.field, error.value.message


def test_reads_pdf_without_password():
    result = read_pdf_text(inter_pdf(SAMPLE), password=None, saved_password=None)
    assert "LOJA X" in result.text
    assert result.opened_with is None


def test_password_required_when_none_given():
    assert _error(LOCKED) == ("password", "Esta fatura tem senha.")


def test_wrong_password():
    assert _error(LOCKED, password="errada") == ("password", "Senha incorreta.")


def test_typed_password_opens_and_is_reported():
    result = read_pdf_text(LOCKED, password="4321", saved_password=None)
    assert "LOJA X" in result.text
    assert result.opened_with == "4321"


def test_saved_password_is_used_when_none_typed():
    assert read_pdf_text(LOCKED, password=None, saved_password="4321").opened_with == "4321"


def test_failed_saved_password_asks_again():
    assert _error(LOCKED, saved_password="errada") == (
        "password",
        "A senha salva não abriu esta fatura. Digite a senha de novo.",
    )


def test_typed_password_wins_over_saved():
    assert read_pdf_text(LOCKED, password="4321", saved_password="errada").opened_with == "4321"


def test_not_a_pdf():
    assert _error(b"ola, eu nao sou um pdf") == ("file", "O arquivo não é um PDF válido.")


def test_too_many_pages():
    assert _error(inter_pdf(SAMPLE, extra_pages=30)) == ("file", "A fatura tem mais de 30 páginas.")
