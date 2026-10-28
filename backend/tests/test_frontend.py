import pytest
from fastapi.testclient import TestClient

from financeiro.app import create_app


@pytest.fixture
def spa_client(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "app.js").write_text("console.log('ok')")
    (tmp_path / "segredo.txt").write_text("não pode vazar")
    settings.frontend_dist = dist
    with TestClient(create_app(settings)) as client:
        yield client


def test_serves_index_and_assets(spa_client):
    assert spa_client.get("/").text == "<html>app</html>"
    assert spa_client.get("/assets/app.js").text == "console.log('ok')"


def test_client_side_routes_fall_back_to_index(spa_client):
    response = spa_client.get("/lancamentos")
    assert response.text == "<html>app</html>"
    assert response.headers["cache-control"] == "no-cache"


def test_unknown_api_route_is_a_json_404(spa_client):
    response = spa_client.get("/api/nao-existe")
    assert response.status_code == 404
    assert response.json()["detail"] == "Recurso não encontrado."


def test_files_outside_dist_are_never_served(spa_client):
    response = spa_client.get("/..%2Fsegredo.txt")
    assert "não pode vazar" not in response.text
