"""Chave do nome de usuário: o que decide se dois nomes são o mesmo (login, primeiro acesso, unicidade)."""

import unicodedata


def username_key(name: str) -> str:
    """Sem acentos, minúsculas e sem espaços nas pontas: "João.Silva " e "joao.silva" são o mesmo usuário."""
    decomposed = unicodedata.normalize("NFKD", name.strip())
    return "".join(char for char in decomposed if not unicodedata.combining(char)).casefold()
