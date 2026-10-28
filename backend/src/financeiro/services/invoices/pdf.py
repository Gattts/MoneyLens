"""Leitura do PDF da fatura em memória. O arquivo e a senha nunca são gravados nem vão para o log."""

import io
from dataclasses import dataclass

from pypdf import PasswordType, PdfReader

from financeiro.errors import AppError, invalid

MAX_PAGES = 30


@dataclass(frozen=True)
class PdfText:
    text: str
    opened_with: str | None  # a senha que abriu o arquivo; None quando ele não tinha senha


def read_pdf_text(data: bytes, *, password: str | None, saved_password: str | None) -> PdfText:
    """Abre o PDF (sem senha, com a digitada ou com a salva, nessa ordem) e extrai o texto em colunas."""
    try:
        reader = PdfReader(io.BytesIO(data))
        opened_with = _unlock(reader, password, saved_password) if reader.is_encrypted else None
        if len(reader.pages) > MAX_PAGES:
            raise invalid("file", f"A fatura tem mais de {MAX_PAGES} páginas.")
        text = "\n".join(page.extract_text(extraction_mode="layout") for page in reader.pages)
    except AppError:
        raise
    except Exception as error:  # o pypdf lança erros variados (KeyError, TypeError…) em PDFs malformados
        raise invalid("file", "O arquivo não é um PDF válido.") from error
    return PdfText(text, opened_with)


def _unlock(reader: PdfReader, password: str | None, saved_password: str | None) -> str | None:
    # Alguns PDFs só têm senha de proprietário (trava de impressão) e abrem com a senha vazia.
    if _opens(reader, ""):
        return None
    if password:
        if _opens(reader, password):
            return password
        raise invalid("password", "Senha incorreta.")
    if saved_password:
        if _opens(reader, saved_password):
            return saved_password
        raise invalid("password", "A senha salva não abriu esta fatura. Digite a senha de novo.")
    raise invalid("password", "Esta fatura tem senha.")


def _opens(reader: PdfReader, candidate: str) -> bool:
    return reader.decrypt(candidate) != PasswordType.NOT_DECRYPTED
