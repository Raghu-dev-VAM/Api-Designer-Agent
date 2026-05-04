"""
Test file examples for the FastAPI application.
Run with: pytest tests.py
"""

import pytest
from fastapi.testclient import TestClient
from main import app


client = TestClient(app)


class TestHealthCheck:
    def test_health_check(self):
        """Test the health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"


class TestValidation:
    def test_validate_valid_openapi(self):
        """Test validation of a valid OpenAPI spec."""
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
        response = client.post("/api/designer/validate", json={"open_api_yaml": valid_yaml})
        assert response.status_code == 200
        result = response.json()
        assert result["is_valid"] is True

    def test_validate_missing_openapi_yaml(self):
        """Test validation with missing OpenAPI YAML."""
        response = client.post("/api/designer/validate", json={"open_api_yaml": ""})
        assert response.status_code == 400

    def test_validate_invalid_yaml(self):
        """Test validation with invalid YAML."""
        invalid_yaml = "invalid: yaml: content:"
        response = client.post("/api/designer/validate", json={"open_api_yaml": invalid_yaml})
        assert response.status_code == 200
        result = response.json()
        assert result["is_valid"] is False

    def test_validate_missing_required_fields(self):
        """Test validation with missing required fields."""
        incomplete_yaml = "openapi: 3.0.3"
        response = client.post("/api/designer/validate", json={"open_api_yaml": incomplete_yaml})
        assert response.status_code == 200
        result = response.json()
        assert result["is_valid"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
