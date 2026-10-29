"""Senhas, chave de sessão, limite de tentativas de login e exigência de usuário logado."""

import hmac
import math
import os
import secrets
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, Request
from sqlalchemy.orm import Session

from financeiro.config import Settings
from financeiro.db import DbSession
from financeiro.errors import AppError
from financeiro.models import User
from financeiro.storage import ensure_private_dir

SESSION_USER_KEY = "uid"
SESSION_VERSION_KEY = "ver"
SECRET_KEY_FILE = "secret_key"  # noqa: S105  # nosec B105 - nome do arquivo, não a chave
MAX_TRACKED_CLIENTS = 10_000

_hasher = PasswordHasher()
# Quando o usuário não existe, a senha é verificada contra este hash. Assim o tempo de resposta é o
# mesmo de uma senha errada e não revela quais usuários existem.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        matches = _hasher.verify(password_hash or _DUMMY_HASH, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    return matches and password_hash is not None


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def load_secret_key(settings: Settings) -> str:
    """Chave que assina o cookie de sessão: FIN_SECRET_KEY ou um arquivo gerado com permissão 600."""
    if settings.secret_key is not None:
        return settings.secret_key.get_secret_value()
    path = settings.data_dir / SECRET_KEY_FILE
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    ensure_private_dir(settings.data_dir)
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:  # outro processo gerou a chave ao mesmo tempo
        return path.read_text(encoding="utf-8").strip()
    key = secrets.token_urlsafe(48)
    with os.fdopen(descriptor, "w", encoding="utf-8") as file:
        file.write(key)
    return key


class LoginRateLimiter:
    """Bloqueia um cliente depois de `max_attempts` falhas dentro de `window_seconds`."""

    def __init__(
        self,
        max_attempts: int,
        window_seconds: int,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_attempts = max_attempts
        self._window = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def retry_after(self, client: str) -> int | None:
        """Segundos até poder tentar de novo, ou None se o cliente não está bloqueado."""
        with self._lock:
            failures = self._recent_failures(client)
            if len(failures) < self._max_attempts:
                return None
            return max(1, math.ceil(failures[0] + self._window - self._clock()))

    def register_failure(self, client: str) -> None:
        with self._lock:
            if len(self._failures) >= MAX_TRACKED_CLIENTS:
                for key in list(self._failures):
                    self._recent_failures(key)
            self._failures.setdefault(client, deque()).append(self._clock())

    def reset(self, client: str) -> None:
        with self._lock:
            self._failures.pop(client, None)

    def _recent_failures(self, client: str) -> deque[float]:
        failures = self._failures.get(client)
        if failures is None:
            return deque()
        oldest_allowed = self._clock() - self._window
        while failures and failures[0] <= oldest_allowed:
            failures.popleft()
        if not failures:
            del self._failures[client]
        return failures


def client_address(request: Request) -> str:
    """IP de quem fez a requisição.

    Atrás do Worker do Cloudflare, o backend só vê o IP do Cloudflare; o Worker envia o IP real em
    X-Forwarded-For. Esse cabeçalho só é aceito com o segredo compartilhado, senão qualquer um o
    forjaria para escapar do limite de tentativas.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded and from_trusted_proxy(request):
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconhecido"


def from_trusted_proxy(request: Request) -> bool:
    """A requisição traz o segredo compartilhado com o Worker do Cloudflare?"""
    secret = request.app.state.settings.proxy_secret
    sent = request.headers.get("x-proxy-secret", "")
    return secret is not None and hmac.compare_digest(sent.encode(), secret.get_secret_value().encode())


def require_trusted_proxy(request: Request) -> None:
    """Com FIN_PROXY_ONLY, a API só atende quem vem pelo Worker: acesso direto ao backend é recusado."""
    if request.app.state.settings.proxy_only and not from_trusted_proxy(request):
        raise AppError("Acesso direto à API não é permitido.", 403)


def session_user(request: Request, session: Session) -> User | None:
    """Usuário do cookie de sessão, se o cookie ainda for válido (mesma versão de sessão do usuário)."""
    user_id = request.session.get(SESSION_USER_KEY)
    user = session.get(User, user_id) if isinstance(user_id, int) else None
    if user is None or user.session_version != request.session.get(SESSION_VERSION_KEY):
        return None
    return user


def require_user(request: Request, session: DbSession) -> User:
    user = session_user(request, session)
    if user is None:
        request.session.clear()
        raise AppError("Faça login para continuar.", 401)
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise AppError("Só administradores podem fazer isso.", 403)
    return user


AdminUser = Annotated[User, Depends(require_admin)]
