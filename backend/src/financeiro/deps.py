"""Dependências compartilhadas pelas rotas."""

from datetime import date
from typing import Annotated

from fastapi import Depends


def get_today() -> date:
    """Data de hoje. Isolada numa dependência para os testes poderem fixar o dia."""
    return date.today()


Today = Annotated[date, Depends(get_today)]
