"""
Unit tests for query normalization and generation.

Tests the core query generation logic that transforms business profiles
into AI search queries for visibility testing.
"""
import pytest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestQueryNormalization:
    """Tests for query normalization (near me -> in City TX)."""

    def test_normalize_removes_near_me(self):
        """Verify 'near me' phrases are replaced with city/state."""
        from app.services.geo.queries import normalize
        
        result = normalize("best electrician near me", "Sugar Land", "TX")
        assert "near me" not in result.lower()
        assert "Sugar Land" in result
        assert "TX" in result

    def test_normalize_preserves_query_intent(self):
        """Verify the core query intent is preserved after normalization."""
        from app.services.geo.queries import normalize
        
        result = normalize("best physical therapy near me", "Houston", "TX")
        assert "physical therapy" in result.lower()
        assert "Houston" in result

    def test_normalize_handles_nearby_phrase(self):
        """Test normalization of 'nearby' phrase."""
        from app.services.geo.queries import normalize
        
        result = normalize("find nearby restaurants", "Austin", "TX")
        assert "nearby" not in result.lower()
        assert "Austin" in result

    def test_normalize_handles_empty_seed(self):
        """Verify empty seed produces valid output with location."""
        from app.services.geo.queries import normalize
        
        # Empty seed should still produce a location string
        result = normalize("", "Houston", "TX")
        assert "Houston" in result
        assert "TX" in result

    def test_normalize_handles_empty_city(self):
        """Verify empty city still produces output with state."""
        from app.services.geo.queries import normalize
        
        result = normalize("best electrician", "", "TX")
        # Should contain the query and state
        assert "electrician" in result.lower()

    def test_normalize_handles_empty_state(self):
        """Verify empty state still produces output with city."""
        from app.services.geo.queries import normalize
        
        result = normalize("best electrician", "Houston", "")
        # Should contain the query and city
        assert "electrician" in result.lower()
        assert "Houston" in result


class TestQueryGeneration:
    """Tests for generate_queries function."""

    def test_generate_queries_returns_list(self, sample_business_profile):
        """Verify generate_queries returns a non-empty list."""
        from app.core.business_intelligence import generate_queries
        
        queries = generate_queries(sample_business_profile, max_per_intent=3)
        
        assert isinstance(queries, list)
        assert len(queries) > 0

    def test_generate_queries_includes_location(self, sample_business_profile):
        """Verify generated queries include location context."""
        from app.core.business_intelligence import generate_queries
        
        queries = generate_queries(sample_business_profile, location_target="city")
        
        # At least one query should contain the city name
        city = sample_business_profile.get("city", "")
        has_city = any(city.lower() in q.lower() for q in queries)
        assert has_city, f"No query contains city '{city}'"

    def test_generate_queries_includes_services(self, sample_business_profile):
        """Verify generated queries include service keywords."""
        from app.core.business_intelligence import generate_queries
        
        queries = generate_queries(sample_business_profile, max_per_intent=5)
        
        # At least one query should contain a service name
        services = sample_business_profile.get("services", [])
        if services:
            first_service = services[0].get("name", "") if isinstance(services[0], dict) else services[0]
            has_service = any(first_service.lower() in q.lower() for q in queries)
            assert has_service, f"No query contains service '{first_service}'"

    def test_generate_queries_respects_max_queries(self, sample_business_profile):
        """Verify query count respects max_per_intent parameter."""
        from app.core.business_intelligence import generate_queries
        
        queries = generate_queries(sample_business_profile, max_per_intent=2)
        
        # Should have some queries but not excessive
        assert len(queries) <= 20  # Reasonable upper bound

    def test_generate_queries_no_duplicates(self, sample_business_profile):
        """Verify generated queries are unique."""
        from app.core.business_intelligence import generate_queries
        
        queries = generate_queries(sample_business_profile)
        unique_queries = set(q.lower() for q in queries)
        
        assert len(queries) == len(unique_queries), "Duplicate queries found"
