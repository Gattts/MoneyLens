"""Configuração lida de variáveis de ambiente com prefixo FIN_ (ou do arquivo backend/.env)."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent
MIN_SECRET_KEY_LENGTH = 32
SUPABASE_HOST_SUFFIXES = (".supabase.co", ".supabase.com")


def normalize_database_url(url: str) -> str:
    """Aceita a URL como o Supabase/Postgres entrega e devolve a forma que o SQLAlchemy usa.

    - `postgres://` e `postgresql://` passam a usar o driver psycopg 3;
    - no Supabase, a conexão exige SSL: sem `sslmode` na URL, usa `require`.
    """
    scheme, _, rest = url.partition("://")
    if scheme in ("postgres", "postgresql"):
        url = f"postgresql+psycopg://{rest}"
    if url.startswith("postgresql+psycopg://") and "sslmode=" not in url:
        host = make_url(url).host or ""
        if host.endswith(SUPABASE_HOST_SUFFIXES):
            url += ("&" if "?" in url else "?") + "sslmode=require"
    return url


class Settings(BaseSettings):
    # env_ignore_empty: uma linha do modelo descomentada sem valor (`FIN_FRONTEND_DIST=`) vale o padrão. Sem
    # isso, o caminho vazio virava a pasta atual e o backend servia arquivos dela, inclusive o .env.
    model_config = SettingsConfigDict(
        env_prefix="FIN_",
        env_file=BACKEND_DIR / ".env",
        env_ignore_empty=True,
        extra="ignore",
        validate_assignment=True,
    )

    data_dir: Path = BACKEND_DIR / "data"
    database_url: str | None = None
    secret_key: SecretStr | None = None
    # Segredo compartilhado com o proxy da frente (Worker do Cloudflare): só com ele o IP real do
    # visitante, enviado em X-Forwarded-For, é aceito (usado no limite de tentativas de login).
    proxy_secret: SecretStr | None = None
    # Com o backend publicado só para o Worker: recusa requisições sem o segredo (exceto /api/health).
    proxy_only: bool = False
    session_max_age_seconds: int = 7 * 24 * 60 * 60
    cookie_secure: bool = False
    allowed_hosts: Annotated[list[str], NoDecode] = ["localhost", "127.0.0.1"]
    # O Render define esta variável com o endereço público do serviço (xxx.onrender.com), que é o Host do
    # health check dele. Sem ela na lista, o health check recebe 400 e o deploy é cancelado.
    render_external_hostname: str | None = Field(default=None, validation_alias="RENDER_EXTERNAL_HOSTNAME")
    enable_docs: bool = False
    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"
    login_max_attempts: int = 5
    login_window_seconds: int = 15 * 60
    # Os corpos da API são JSON pequenos; 1 MiB sobra e impede esgotar a memória com uploads gigantes.
    max_body_bytes: int = 1024 * 1024

    @field_validator("secret_key", "proxy_secret")
    @classmethod
    def _require_long_secret(cls, value: SecretStr | None) -> SecretStr | None:
        # Uma chave curta pode ser adivinhada, e quem a conhece forja cookies de sessão.
        if value is not None and len(value.get_secret_value()) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(f"O segredo precisa ter pelo menos {MIN_SECRET_KEY_LENGTH} caracteres.")
        return value

    @field_validator("allowed_hosts", mode="before")
    @classmethod
    def _split_hosts(cls, value: object) -> object:
        if isinstance(value, str):
            return [host.strip() for host in value.split(",") if host.strip()]
        return value

    @model_validator(mode="after")
    def _proxy_only_needs_secret(self) -> "Settings":
        if self.proxy_only and self.proxy_secret is None:
            raise ValueError("FIN_PROXY_ONLY=true exige FIN_PROXY_SECRET.")
        return self

    @property
    def trusted_hosts(self) -> list[str]:
        extra = [self.render_external_hostname] if self.render_external_hostname else []
        return [*self.allowed_hosts, *extra]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return normalize_database_url(self.database_url)
        return f"sqlite:///{self.data_dir / 'financeiro.db'}"


@lru_cache
def get_settings() -> Settings:
    return Settings()
