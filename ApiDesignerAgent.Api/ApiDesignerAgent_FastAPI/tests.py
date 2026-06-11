"""
Test file — run with: pytest tests.py -v
"""
import asyncio
import csv
import io
import json
import pytest
import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy import delete
from database import AsyncSessionLocal, User, init_db
from main import app


def _make_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode()


def _make_xlsx(rows: list[dict]) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row[h] for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


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


SAMPLE_ROWS = [
    {
        "Story ID": "US-001",
        "Epic": "User Management",
        "User Story": "As a user I want to register an account",
        "Priority": "High",
        "Acceptance Criteria": "Email is unique; Password meets policy",
    },
    {
        "Story ID": "US-002",
        "Epic": "User Management",
        "User Story": "As a user I want to list all products",
        "Priority": "Medium",
        "Acceptance Criteria": "Returns paginated results",
    },
]


class TestExcelExtract:
    def test_csv_no_mapping(self, client):
        r = client.post(
            "/api/excel/extract-requirements",
            files={"file": ("test.csv", _make_csv(SAMPLE_ROWS), "text/csv")},
        )
        assert r.status_code == 200
        reqs = r.json()["requirements"]
        assert len(reqs) == 2
        assert reqs[0]["priority"] == "High"

    def test_xlsx_no_mapping(self, client):
        r = client.post(
            "/api/excel/extract-requirements",
            files={"file": ("test.xlsx", _make_xlsx(SAMPLE_ROWS), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
        assert r.status_code == 200
        assert len(r.json()["requirements"]) == 2

    def test_csv_with_mapping(self, client):
        mapping = json.dumps({
            "storyId": "Story ID",
            "title": "Epic",
            "userStory": "User Story",
            "priority": "Priority",
            "acceptanceCriteria": "Acceptance Criteria",
            "epic": "Epic",
        })
        r = client.post(
            "/api/excel/extract-requirements",
            files={"file": ("test.csv", _make_csv(SAMPLE_ROWS), "text/csv")},
            data={"mapping": mapping},
        )
        assert r.status_code == 200
        reqs = r.json()["requirements"]
        assert reqs[0]["title"] == "User Management"
        assert "Email is unique" in reqs[0]["desc"]

    def test_invalid_extension(self, client):
        r = client.post(
            "/api/excel/extract-requirements",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert r.status_code == 400
        assert "xlsx" in r.json()["detail"]

    def test_empty_file(self, client):
        r = client.post(
            "/api/excel/extract-requirements",
            files={"file": ("empty.csv", b"", "text/csv")},
        )
        assert r.status_code == 400

    def test_invalid_mapping_json(self, client):
        r = client.post(
            "/api/excel/extract-requirements",
            files={"file": ("test.csv", _make_csv(SAMPLE_ROWS), "text/csv")},
            data={"mapping": "not-valid-json"},
        )
        assert r.status_code == 400
        assert "mapping" in r.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
