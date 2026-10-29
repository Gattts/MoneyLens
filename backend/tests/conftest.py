import os
from collections.abc import Iterator
from datetime import UTC, date, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from financeiro.app import create_app
from financeiro.config import Settings
from financeiro.deps import get_today
from financeiro.models import Base, User
from financeiro.security import hash_password
from tests.factories import create_card, create_category

TODAY = date(2026, 10, 27)
USERNAME = "ana"
SECOND_USERNAME = "bia"
PASSWORD = "senha-segura-123"
# Defina para rodar a suíte num Postgres de verdade (ex.: o mesmo usado pelo Supabase).
TEST_DATABASE_URL = os.environ.get("FIN_TEST_DATABASE_URL")


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        data_dir=tmp_path,
        database_url=TEST_DATABASE_URL or "sqlite://",
        secret_key="chave-de-teste-nao-usar-em-producao",
        allowed_hosts=["testserver"],
        frontend_dist=tmp_path / "sem-frontend",
    )


@pytest.fixture
def app(settings) -> Iterator[FastAPI]:
    application = create_app(settings)
    engine = application.state.engine
    Base.metadata.drop_all(engine)  # no Postgres o banco persiste entre testes
    Base.metadata.create_all(engine)
    application.dependency_overrides[get_today] = lambda: TODAY
    yield application
    engine.dispose()


@pytest.fixture
def db(app) -> Iterator[Session]:
    with app.state.sessionmaker() as session:
        yield session


@pytest.fixture
def user(db) -> User:
    account = User(
        username=USERNAME,
        username_key=USERNAME,
        password_hash=hash_password(PASSWORD),
        is_admin=True,
        activated_at=datetime.now(UTC),
    )
    db.add(account)
    db.commit()
    return account


@pytest.fixture
def second_user(db) -> User:
    account = User(
        username=SECOND_USERNAME,
        username_key=SECOND_USERNAME,
        password_hash=hash_password(PASSWORD),
        activated_at=datetime.now(UTC),
    )
    db.add(account)
    db.commit()
    return account


@pytest.fixture
def other_client(app, second_user) -> Iterator[TestClient]:
    """Outro usuário logado, com cookies próprios: serve para provar que um não vê os dados do outro."""
    with TestClient(app) as other:
        response = other.post("/api/auth/login", json={"username": SECOND_USERNAME, "password": PASSWORD})
        assert response.status_code == 200, response.text
        yield other


@pytest.fixture
def anon_client(app) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(anon_client, user) -> TestClient:
    response = anon_client.post("/api/auth/login", json={"username": USERNAME, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return anon_client


@pytest.fixture
def card(client) -> dict:
    return create_card(client, name="Inter")


@pytest.fixture
def transport(client) -> dict:
    """Categoria "Transporte" com a regra "contém UBER" (o banco dos testes não tem o dicionário inicial)."""
    category = create_category(client, name="Transporte", default_bucket="needs")
    rule = {"pattern": "UBER", "match_type": "contains", "category_id": category["id"]}
    assert client.post("/api/category-rules", json=rule).status_code == 201
    return category
