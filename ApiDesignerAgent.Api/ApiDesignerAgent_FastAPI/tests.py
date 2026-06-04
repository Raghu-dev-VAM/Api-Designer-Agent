"""
Test file — run with: pytest tests.py -v
"""
import asyncio
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from database import AsyncSessionLocal, User, init_db
from main import app


asyncio.run(init_db())


def _clean(*usernames):
    async def _c():
        async with AsyncSessionLocal() as db:
            for u in usernames:
                await db.execute(delete(User).where(User.username == u))
            await db.commit()
    asyncio.run(_c())


@pytest.fixture(scope="module")
def client():
    _clean("pytest_user")
    with TestClient(app, raise_server_exceptions=False) as c:
        # Register once for the whole module
        c.post("/api/auth/register", json={
            "username": "pytest_user", "email": "pytest@test.com", "password": "pytest1234"
        })
        yield c
    _clean("pytest_user")


@pytest.fixture(scope="module")
def auth_headers(client):
    r = client.post("/api/auth/login", data={"username": "pytest_user", "password": "pytest1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


class TestHealthCheck:
    def test_health_check(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"


class TestAuth:
    def test_register(self, client):
        _clean("reg_pytest")
        r = client.post("/api/auth/register", json={
            "username": "reg_pytest", "email": "reg_pytest@test.com", "password": "reg12345"
        })
        assert r.status_code == 201
        assert r.json()["username"] == "reg_pytest"
        _clean("reg_pytest")

    def test_login(self, client):
        r = client.post("/api/auth/login", data={"username": "pytest_user", "password": "pytest1234"})
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_me(self, client, auth_headers):
        r = client.get("/api/auth/me", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["username"] == "pytest_user"

    def test_me_no_token(self, client):
        r = client.get("/api/auth/me")
        assert r.status_code == 401


class TestValidation:
    def test_validate_valid_openapi(self, client, auth_headers):
        valid_yaml = """
openapi: 3.0.3
info:
  title: Test API
  version: 1.0.0
paths:
  /test:
    get:
      summary: Get test
      responses:
        '200':
          description: Success
"""
        r = client.post("/api/designer/validate", json={"open_api_yaml": valid_yaml}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["is_valid"] is True

    def test_validate_missing_yaml(self, client, auth_headers):
        r = client.post("/api/designer/validate", json={"open_api_yaml": ""}, headers=auth_headers)
        assert r.status_code == 400

    def test_validate_invalid_yaml(self, client, auth_headers):
        r = client.post("/api/designer/validate", json={"open_api_yaml": "invalid: yaml: content:"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["is_valid"] is False

    def test_validate_missing_fields(self, client, auth_headers):
        r = client.post("/api/designer/validate", json={"open_api_yaml": "openapi: 3.0.3"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["is_valid"] is False

    def test_validate_requires_auth(self, client):
        r = client.post("/api/designer/validate", json={"open_api_yaml": "openapi: 3.0.3"})
        assert r.status_code == 401


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
