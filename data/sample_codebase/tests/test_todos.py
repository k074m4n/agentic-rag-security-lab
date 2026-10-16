import pytest

from app import create_app
from app.config import TestConfig

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def client(tmp_path):
    class Config(TestConfig):
        DATABASE_PATH = str(tmp_path / "test.sqlite3")

    app = create_app(Config)
    with app.test_client() as client:
        yield client


def test_create_requires_token(client):
    resp = client.post("/api/v1/todos", json={"title": "write docs"})
    assert resp.status_code == 401


def test_create_and_get(client):
    created = client.post("/api/v1/todos", json={"title": "write docs"}, headers=AUTH)
    assert created.status_code == 201
    todo_id = created.get_json()["id"]

    fetched = client.get(f"/api/v1/todos/{todo_id}")
    assert fetched.get_json()["title"] == "write docs"


def test_empty_title_rejected(client):
    resp = client.post("/api/v1/todos", json={"title": "   "}, headers=AUTH)
    assert resp.status_code == 400


def test_invalid_page_rejected(client):
    assert client.get("/api/v1/todos?page=0").status_code == 400
