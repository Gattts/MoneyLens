"""Dependências compartilhadas pelas rotas."""

from datetime import date


def get_today() -> date:
    """Data de hoje. Isolada numa dependência para os testes poderem fixar o dia."""
    return date.today()
