import pytest
from pydantic import ValidationError

from financeiro.config import Settings


def test_short_secret_key_is_refused():
    with pytest.raises(ValidationError, match="pelo menos 32 caracteres"):
        Settings(_env_file=None, secret_key="curta-demais")


def test_allowed_hosts_accept_comma_separated_text(monkeypatch):
    monkeypatch.setenv("FIN_ALLOWED_HOSTS", "financeiro.exemplo.com, 127.0.0.1")
    assert Settings(_env_file=None).allowed_hosts == ["financeiro.exemplo.com", "127.0.0.1"]


def test_empty_values_in_env_file_mean_default(tmp_path):
    # Quem descomenta uma linha do modelo sem preencher o valor fica com o padrão, não com "" ou ".".
    env_file = tmp_path / ".env"
    env_file.write_text("FIN_FRONTEND_DIST=\nFIN_SECRET_KEY=\n")
    settings = Settings(_env_file=env_file)
    assert settings.frontend_dist == Settings(_env_file=None).frontend_dist
    assert settings.secret_key is None


def test_render_public_hostname_is_trusted(monkeypatch):
    # O nome xxx.onrender.com só é conhecido depois de criar o serviço; o Render o informa nesta variável.
    monkeypatch.setenv("RENDER_EXTERNAL_HOSTNAME", "financeiro-api.onrender.com")
    assert Settings(_env_file=None).trusted_hosts == ["localhost", "127.0.0.1", "financeiro-api.onrender.com"]


def test_outside_render_only_allowed_hosts_are_trusted(monkeypatch):
    monkeypatch.delenv("RENDER_EXTERNAL_HOSTNAME", raising=False)
    assert Settings(_env_file=None).trusted_hosts == ["localhost", "127.0.0.1"]


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        # Formatos que o painel do Supabase entrega (pooler de sessão e conexão direta).
        (
            "postgresql://postgres.abcd:s3nh%40@aws-0-sa-east-1.pooler.supabase.com:5432/postgres",
            "postgresql+psycopg://postgres.abcd:s3nh%40@aws-0-sa-east-1.pooler.supabase.com:5432/postgres?sslmode=require",
        ),
        (
            "postgres://postgres:x@db.abcd.supabase.co:5432/postgres",
            "postgresql+psycopg://postgres:x@db.abcd.supabase.co:5432/postgres?sslmode=require",
        ),
        # Postgres local: sem SSL forçado; quem já escolheu o sslmode é respeitado.
        (
            "postgresql://app:x@localhost:5432/financeiro",
            "postgresql+psycopg://app:x@localhost:5432/financeiro",
        ),
        (
            "postgresql://app:x@db.abcd.supabase.co/postgres?sslmode=verify-full",
            "postgresql+psycopg://app:x@db.abcd.supabase.co/postgres?sslmode=verify-full",
        ),
    ],
)
def test_postgres_urls_get_driver_and_ssl(given, expected):
    assert Settings(_env_file=None, database_url=given).resolved_database_url == expected


def test_without_database_url_uses_local_sqlite(tmp_path):
    settings = Settings(_env_file=None, data_dir=tmp_path)
    assert settings.resolved_database_url == f"sqlite:///{tmp_path / 'financeiro.db'}"
