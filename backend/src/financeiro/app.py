"""Criação da aplicação FastAPI."""

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import sessionmaker
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from financeiro.config import Settings, get_settings
from financeiro.db import create_db_engine
from financeiro.errors import register_error_handlers
from financeiro.limits import BodySizeLimitMiddleware
from financeiro.routers import (
    admin,
    auth,
    budget,
    cards,
    categories,
    goals,
    invoices,
    recurring,
    rules,
    summary,
    transactions,
)
from financeiro.security import LoginRateLimiter, load_secret_key, require_trusted_proxy, require_user
from financeiro.storage import ensure_private_dir

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
    "font-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)
PROTECTED_ROUTERS: list[APIRouter] = [
    categories.router,
    cards.router,
    cards.payments_router,
    goals.router,
    transactions.router,
    recurring.router,
    budget.router,
    summary.router,
    rules.router,
    invoices.imports_router,
    invoices.lines_router,
    admin.router,
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    if settings.database_url is None:
        ensure_private_dir(settings.data_dir)
    engine = create_db_engine(settings.resolved_database_url)

    app = FastAPI(
        title="Financeiro",
        docs_url="/api/docs" if settings.enable_docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if settings.enable_docs else None,
    )
    app.state.settings = settings
    app.state.engine = engine
    app.state.sessionmaker = sessionmaker(engine, expire_on_commit=False)
    app.state.login_limiter = LoginRateLimiter(settings.login_max_attempts, settings.login_window_seconds)

    register_error_handlers(app)
    # A ordem importa: cada add_middleware envolve os anteriores. O limite de corpo fica por dentro dos
    # cabeçalhos de segurança (a resposta 413 também os recebe) e antes de qualquer leitura do corpo.
    app.add_middleware(
        BodySizeLimitMiddleware,
        max_bytes=settings.max_body_bytes,
        path_limits={"/api/invoice-imports": settings.max_upload_bytes},
    )
    app.middleware("http")(_security_headers)
    app.add_middleware(
        SessionMiddleware,
        secret_key=load_secret_key(settings),
        session_cookie="fin_session",
        max_age=settings.session_max_age_seconds,
        same_site="strict",
        https_only=settings.cookie_secure,
    )
    # Adicionado por último para ser o primeiro a rodar: barra Host desconhecido (DNS rebinding).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

    app.include_router(_api_router())
    # Só uma pasta de build (com index.html) é servida: apontar para outra pasta exporia os arquivos dela.
    if (settings.frontend_dist / "index.html").is_file():
        _serve_frontend(app, settings.frontend_dist)
    return app


def _serve_frontend(app: FastAPI, dist: Path) -> None:
    """Serve o build do React na mesma origem da API; rotas desconhecidas caem no index.html (SPA)."""
    dist = dist.resolve()
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise StarletteHTTPException(status_code=404)
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        # Sem cache: um build novo precisa ser visto logo; os assets têm hash no nome e podem ser cacheados.
        return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})


def _api_router() -> APIRouter:
    api = APIRouter(prefix="/api")
    # O health check da plataforma fica livre; o resto passa pela checagem do proxy (FIN_PROXY_ONLY).
    api.add_api_route("/health", _health, methods=["GET"], include_in_schema=False)
    gated = APIRouter(dependencies=[Depends(require_trusted_proxy)])
    gated.include_router(auth.router)
    protected = APIRouter(dependencies=[Depends(require_user)])
    for router in PROTECTED_ROUTERS:
        protected.include_router(router)
    gated.include_router(protected)
    api.include_router(gated)
    return api


def _health() -> dict[str, str]:
    return {"status": "ok"}


async def _security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if request.app.state.settings.cookie_secure:
        # Só faz sentido (e só é seguro ligar) quando o acesso é por HTTPS.
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response
