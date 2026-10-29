"""Pedaços comuns aos leitores de extrato: meses por extenso, valores em reais e nomes comparáveis."""

import unicodedata

FULL_MONTHS = {
    "JANEIRO": 1, "FEVEREIRO": 2, "MARÇO": 3, "ABRIL": 4, "MAIO": 5, "JUNHO": 6,
    "JULHO": 7, "AGOSTO": 8, "SETEMBRO": 9, "OUTUBRO": 10, "NOVEMBRO": 11, "DEZEMBRO": 12,
}  # fmt: skip
VALUE = r"\d{1,3}(?:\.\d{3})*,\d{2}"


def cents(value: str) -> int:
    """Valor como "1.234,56" em centavos."""
    return int(value.replace(".", "").replace(",", ""))


def plain(text: str) -> str:
    """Maiúsculas, sem acentos e com espaços simples, para comparar nomes."""
    decomposed = unicodedata.normalize("NFKD", text.upper())
    return " ".join("".join(char for char in decomposed if not unicodedata.combining(char)).split())
