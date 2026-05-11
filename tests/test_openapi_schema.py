"""Smoke tests for the drf-spectacular OpenAPI schema."""

import pytest
import yaml


@pytest.mark.django_db
class TestSchemaEndpoint:
    """GET /api/schema/ — public, returns OpenAPI 3 YAML."""

    def test_schema_returns_200(self, api_client):
        resp = api_client.get("/api/schema/")
        assert resp.status_code == 200

    def test_schema_parses_as_yaml(self, api_client):
        resp = api_client.get("/api/schema/")
        # DRF/Spectacular returns the YAML body as bytes.
        parsed = yaml.safe_load(resp.content)
        assert parsed["openapi"].startswith("3.")
        assert parsed["info"]["title"] == "OpenChapters API"
        assert "paths" in parsed
        # Sanity: the spec covers the chapter listing endpoint at minimum.
        assert "/api/chapters/" in parsed["paths"]

    def test_swagger_ui_loads(self, api_client):
        resp = api_client.get("/api/schema/swagger-ui/")
        assert resp.status_code == 200
        assert b"swagger" in resp.content.lower()

    def test_redoc_loads(self, api_client):
        resp = api_client.get("/api/schema/redoc/")
        assert resp.status_code == 200
        assert b"redoc" in resp.content.lower()
