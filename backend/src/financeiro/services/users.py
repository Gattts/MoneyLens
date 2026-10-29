"""Usuários: pacote padrão de cada conta nova, convites e primeiro acesso."""

import re
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from financeiro.domain.defaults import DEFAULT_BUDGET, DEFAULT_CATEGORIES, DEFAULT_RULES
from financeiro.domain.enums import Bucket, Kind, MatchType, RuleSource
from financeiro.domain.usernames import username_key
from financeiro.errors import conflict, invalid
from financeiro.models import BudgetSettings, Category, CategoryRule, User
from financeiro.security import hash_password, verify_password

INVITE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I/L, que se confundem ao digitar
INVITE_LENGTH = 8
INVITE_DAYS = 7
MIN_USERNAME_LENGTH, MAX_USERNAME_LENGTH = 3, 50
MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH = 8, 128
USERNAME_KEY_PATTERN = re.compile(r"[a-z0-9._-]+")
USERNAME_RULE = "Use de 3 a 50 caracteres: letras, números, ponto, hífen ou sublinhado, sem espaços."
PASSWORD_RULE = "Use de 8 a 128 caracteres."  # noqa: S105  # nosec B105 - texto de ajuda
DUPLICATE_USERNAME = "Já existe um usuário com esse nome."

UserStatus = Literal["active", "pending", "expired"]


def seed_defaults(session: Session, user_id: int) -> None:
    """Cria as categorias, as palavras-chave das faturas e o orçamento 50/30/20 do usuário (sem commit)."""
    categories = [
        Category(
            user_id=user_id,
            icon=icon,
            name=name,
            kind=Kind(kind),
            default_bucket=Bucket(bucket) if bucket else None,
            description=description,
        )
        for icon, name, kind, bucket, description in DEFAULT_CATEGORIES
    ]
    session.add_all(categories)
    session.flush()
    ids = {category.name: category.id for category in categories}
    session.add_all(
        CategoryRule(
            user_id=user_id,
            pattern=pattern,
            match_type=MatchType.CONTAINS,
            category_id=ids[name],
            source=RuleSource.DEFAULT,
        )
        for pattern, name in DEFAULT_RULES
        if name in ids
    )
    needs, wants, savings = DEFAULT_BUDGET
    session.add(BudgetSettings(user_id=user_id, needs_pct=needs, wants_pct=wants, savings_pct=savings))


def new_invite_code() -> str:
    raw = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))
    return f"{raw[:4]}-{raw[4:]}"


def normalize_code(text: str) -> str:
    """Aceita o código digitado com hífen, espaços ou em minúsculas."""
    return "".join(text.split()).replace("-", "").upper()


def validate_username(name: str) -> str:
    """Nome sem espaços nas pontas; recusa espaços, símbolos e letras de outros alfabetos (sósias)."""
    name = name.strip()
    if not MIN_USERNAME_LENGTH <= len(name) <= MAX_USERNAME_LENGTH or not USERNAME_KEY_PATTERN.fullmatch(
        username_key(name)
    ):
        raise invalid("username", USERNAME_RULE)
    return name


def validate_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise invalid("password", PASSWORD_RULE)


def find_user(session: Session, username: str) -> User | None:
    return session.scalar(select(User).where(User.username_key == username_key(username)))


def issue_invite(user: User, now: datetime) -> str:
    """Novo convite: a senha atual deixa de valer e as sessões caem. Devolve o código (só desta vez)."""
    code = new_invite_code()
    user.invite_code_hash = hash_password(normalize_code(code))
    user.invite_expires_at = now + timedelta(days=INVITE_DAYS)
    user.password_hash = hash_password(secrets.token_urlsafe(32))
    user.activated_at = None
    user.session_version += 1
    return code


def create_pending_user(session: Session, username: str, now: datetime) -> tuple[User, str]:
    name = validate_username(username)
    if find_user(session, name) is not None:
        raise conflict(DUPLICATE_USERNAME)
    user = User(username=name, username_key=username_key(name), session_version=1)
    code = issue_invite(user, now)
    session.add(user)
    try:
        session.flush()
        seed_defaults(session, user.id)
        session.commit()
    except (
        IntegrityError
    ) as error:  # dois cadastros do mesmo nome ao mesmo tempo: a chave única barra o segundo
        session.rollback()
        raise conflict(DUPLICATE_USERNAME) from error
    return user, code


def activate_user(session: Session, username: str, code: str, password: str, now: datetime) -> User | None:
    """Primeiro acesso. None em qualquer recusa (mesmo tempo e mesma mensagem para usuário inexistente)."""
    user = find_user(session, username)
    pending = user is not None and user_status(user, now) == "pending"
    code_ok = verify_password(user.invite_code_hash if user and pending else None, normalize_code(code))
    if user is None or not (pending and code_ok):
        return None
    user.password_hash = hash_password(password)
    user.activated_at = now
    user.invite_code_hash = user.invite_expires_at = None
    user.session_version += 1
    return user


def user_status(user: User, now: datetime) -> UserStatus:
    if user.activated_at is not None:
        return "active"
    expires = user.invite_expires_at
    if user.invite_code_hash is None or expires is None:
        return "expired"
    # O SQLite devolve a data sem fuso; tudo é gravado em UTC.
    return "pending" if (expires if expires.tzinfo else expires.replace(tzinfo=UTC)) > now else "expired"
