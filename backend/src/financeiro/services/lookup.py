"""Buscas por id e comparação de nomes."""

import unicodedata
from collections.abc import Iterable

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.orm import Session

from financeiro.errors import conflict, not_found
from financeiro.models import Base, Category, CreditCard, Goal

NamedModel = Category | CreditCard | Goal


def get_or_404[ModelT: Base](session: Session, model: type[ModelT], item_id: int, message: str) -> ModelT:
    item = session.get(model, item_id)
    if item is None:
        raise not_found(message)
    return item


def name_key(text: str) -> str:
    """Chave que ignora maiúsculas, acentos e espaços nas pontas: "Saúde " e "saude" empatam."""
    normalized = unicodedata.normalize("NFKD", text.strip().casefold())
    return "".join(char for char in normalized if not unicodedata.combining(char))


def name_taken(name: str, existing: Iterable[tuple[int, str]], exclude_id: int | None = None) -> bool:
    key = name_key(name)
    return any(name_key(other) == key for other_id, other in existing if other_id != exclude_id)


def ensure_unique_name(
    session: Session,
    model: type[NamedModel],
    name: str,
    message: str,
    *,
    user_id: int,
    exclude_id: int | None = None,
) -> None:
    """Nome repetido entre os itens do mesmo usuário (pessoas diferentes podem ter um cartão "Nubank")."""
    existing = session.execute(select(model.id, model.name).where(model.user_id == user_id)).all()
    if name_taken(name, existing, exclude_id):
        raise conflict(message)


def count_references(session: Session, *conditions: ColumnElement[bool]) -> int:
    """Soma, entre tabelas, quantas linhas apontam para algo; usado antes de permitir excluir."""
    return sum(session.scalar(select(func.count()).where(condition)) or 0 for condition in conditions)
