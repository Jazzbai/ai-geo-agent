"""
Integration tests for FastAPI endpoints.

Tests the API endpoints with mocked dependencies to ensure
proper request/response handling without external API calls.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from fastapi.testclient import TestClient


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_returns_200(self):
        """Verify health endpoint returns 200 OK."""
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_root_returns_api_info(self):
        """Verify root endpoint returns API information."""
        from app.main import app
        client = TestClient(app)
        
        response = client.get("/")
        
        assert response.status_code == 200
        assert "message" in response.json()
        assert "endpoints" in response.json()


class TestGeoEndpoints:
    """Tests for GEO visibility endpoints."""

    def test_full_pipeline_validates_location_target(self):
        """Verify full-pipeline rejects invalid location_target."""
        from app.main import app
        client = TestClient(app)
        
        response = client.post(
            "/api/v1/geo/full-pipeline",
            json={
                "url": "https://example.com",
                "location_target": "invalid_target"
            }
        )
        
        assert response.status_code == 400
        assert "location_target" in response.json()["detail"]

    def test_full_pipeline_validates_mode(self):
        """Verify full-pipeline rejects invalid mode."""
        from app.main import app
        client = TestClient(app)
        
        response = client.post(
            "/api/v1/geo/full-pipeline",
            json={
                "url": "https://example.com",
                "mode": "invalid_mode"
            }
        )
        
        assert response.status_code == 400
        assert "mode" in response.json()["detail"]

    def test_business_profile_requires_url(self):
        """Verify business-profile requires URL field."""
        from app.main import app
        client = TestClient(app)
        
        response = client.post(
            "/api/v1/geo/business-profile",
            json={}
        )
        
        # Should fail validation (422) due to missing required field
        assert response.status_code == 422


class TestRequestValidation:
    """Tests for request body validation."""

    def test_pipeline_accepts_valid_request(self):
        """Verify pipeline accepts valid request structure."""
        from app.main import app
        from app.api.geo import PipelineRequest
        
        # This should not raise
        request = PipelineRequest(
            url="https://example.com",
            model="gpt-4o-mini",
            max_queries=10,
            location_target="city",
            mode="evaluate",
            competitors=["Competitor A"]
        )
        
        assert request.url == "https://example.com"
        assert request.mode == "evaluate"

    def test_visibility_score_request_defaults(self):
        """Verify visibility score request has correct defaults."""
        from app.api.geo import VisibilityScoreRequest
        
        request = VisibilityScoreRequest(
            profile={"business_name": "Test"}
        )
        
        assert request.model == "gpt-4o-mini"
        assert request.max_queries == 10
        assert request.location_target == "city"
        assert request.mode == "evaluate"
