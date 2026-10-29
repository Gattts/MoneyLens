import logging
import math
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, StringConstraints

from financeiro.db import DbSession
from financeiro.errors import AppError
from financeiro.models import User
from financeiro.schemas.users import ActivateIn
from financeiro.security import (
    SESSION_USER_KEY,
    SESSION_VERSION_KEY,
    CurrentUser,
    LoginRateLimiter,
    client_address,
    hash_password,
    needs_rehash,
    session_user,
    verify_password,
)
from financeiro.services.users import activate_user, find_user, validate_password

router = APIRouter(prefix="/auth", tags=["autenticação"])
logger = logging.getLogger(__name__)


class LoginIn(BaseModel):
    # Sem strip na senha: espaços fazem parte dela.
    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class MeOut(BaseModel):
    username: str
    is_admin: bool


@router.post("/login")
def login(body: LoginIn, request: Request, session: DbSession) -> MeOut:
    limiter: LoginRateLimiter = request.app.state.login_limiter
    client = client_address(request)
    _ensure_not_throttled(limiter, client)

    user = find_user(session, body.username)
    password_ok = verify_password(user.password_hash if user else None, body.password)
    if user is None or user.activated_at is None or not password_ok:
        limiter.register_failure(client)
        raise AppError("Usuário ou senha incorretos.", 401, code="invalid_credentials")

    limiter.reset(client)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        session.commit()
    return _open_session(request, user)


@router.post("/logout", status_code=204)
def logout(request: Request, session: DbSession) -> None:
    """Encerra a sessão em todos os aparelhos: invalida qualquer cópia do cookie, não só a deste navegador."""
    user = session_user(request, session)
    if user is not None:
        user.session_version += 1
        session.commit()
    request.session.clear()


@router.get("/me")
def me(user: CurrentUser) -> MeOut:
    return MeOut(username=user.username, is_admin=user.is_admin)


@router.post("/activate")
def activate(body: ActivateIn, request: Request, session: DbSession) -> MeOut:
    """Primeiro acesso: usuário + código de convite; a pessoa escolhe a senha e já entra."""
    limiter: LoginRateLimiter = request.app.state.login_limiter
    client = client_address(request)
    _ensure_not_throttled(limiter, client)
    validate_password(body.password)
    user = activate_user(session, body.username, body.code, body.password, datetime.now(UTC))
    if user is None:
        limiter.register_failure(client)
        raise AppError("Usuário ou código inválido, ou o convite expirou.", 401, code="invite_refused")
    limiter.reset(client)
    session.commit()
    logger.info("Conta %d ativada", user.id)
    return _open_session(request, user)


def _open_session(request: Request, user: User) -> MeOut:
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id
    request.session[SESSION_VERSION_KEY] = user.session_version
    return MeOut(username=user.username, is_admin=user.is_admin)


def _ensure_not_throttled(limiter: LoginRateLimiter, client: str) -> None:
    """Login e primeiro acesso dividem o limite de tentativas por IP."""
    wait_seconds = limiter.retry_after(client)
    if wait_seconds is not None:
        minutes = math.ceil(wait_seconds / 60)
        raise AppError(
            f"Muitas tentativas de login. Tente de novo em {minutes} minuto(s).",
            429,
            headers={"Retry-After": str(wait_seconds)},
        )
