import math
from typing import Annotated

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select

from financeiro.db import DbSession
from financeiro.errors import AppError
from financeiro.models import User
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

router = APIRouter(prefix="/auth", tags=["autenticação"])


class LoginIn(BaseModel):
    # Sem strip na senha: espaços fazem parte dela.
    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class MeOut(BaseModel):
    username: str


@router.post("/login")
def login(body: LoginIn, request: Request, session: DbSession) -> MeOut:
    limiter: LoginRateLimiter = request.app.state.login_limiter
    client = client_address(request)
    wait_seconds = limiter.retry_after(client)
    if wait_seconds is not None:
        minutes = math.ceil(wait_seconds / 60)
        raise AppError(
            f"Muitas tentativas de login. Tente de novo em {minutes} minuto(s).",
            429,
            headers={"Retry-After": str(wait_seconds)},
        )

    user = session.scalar(select(User).where(User.username == body.username))
    password_ok = verify_password(user.password_hash if user else None, body.password)
    if user is None or not password_ok:
        limiter.register_failure(client)
        raise AppError("Usuário ou senha incorretos.", 401)

    limiter.reset(client)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        session.commit()
    request.session.clear()
    request.session[SESSION_USER_KEY] = user.id
    request.session[SESSION_VERSION_KEY] = user.session_version
    return MeOut(username=user.username)


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
    return MeOut(username=user.username)
