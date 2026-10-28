"""Nome normalizado do estabelecimento, usado para comparar linhas de fatura e regras."""

import re
import unicodedata

INSTALLMENT_SUFFIX = re.compile(r"\(PARCELA \d+ DE \d+\)\s*$")


def merchant_key(description: str) -> str:
    """Maiúsculas, sem acentos, sem "(Parcela k de N)" e com espaços únicos; a pontuação (*, ., /) fica."""
    decomposed = unicodedata.normalize("NFKD", description.upper())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(INSTALLMENT_SUFFIX.sub("", " ".join(plain.split())).split())
