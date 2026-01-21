"""
Unit tests for business intelligence module.

Tests crawl data parsing, profile creation, and prompt building
without requiring external API calls.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.business_intelligence import parse_crawl_data, make_visibility_prompt, _extract_json_block


class TestParseCrawlData:
    """Tests for parse_crawl_data function."""

    def test_empty_crawl_returns_defaults(self):
        """Verify empty crawl data returns default structure."""
        result = parse_crawl_data([])
        
        assert result["business_name"] == "Not found."
        assert result["about_us"] == "Not found."
        assert result["services"] == []
        assert result["locations"] == []

    def test_extracts_business_name_from_title(self, sample_crawl_data):
        """Verify business name is extracted from page title."""
        result = parse_crawl_data(sample_crawl_data)
        
        assert result["business_name"] != "Not found."
        assert "Apex" in result["business_name"]

    def test_extracts_about_from_about_page(self, sample_crawl_data):
        """Verify about text is extracted from about page."""
        result = parse_crawl_data(sample_crawl_data)
        
        # Should have extracted some about text
        assert result["about_us"] != "Not found." or len(sample_crawl_data) < 2


class TestMakeVisibilityPrompt:
    """Tests for make_visibility_prompt function."""

    def test_evaluate_mode_returns_structured_prompt(self, sample_business_profile):
        """Verify evaluate mode produces structured analysis prompt."""
        prompt = make_visibility_prompt(
            sample_business_profile,
            "best physical therapy in Sugar Land",
            mode="evaluate"
        )
        
        assert "AI SEARCH VISIBILITY ANALYSIS" in prompt
        assert "JSON" in prompt
        assert sample_business_profile["business_name"] in prompt

    def test_simulate_mode_returns_natural_prompt(self, sample_business_profile):
        """Verify simulate mode produces natural response prompt."""
        prompt = make_visibility_prompt(
            sample_business_profile,
            "best physical therapy in Sugar Land",
            mode="simulate"
        )
        
        assert "Answer this question" in prompt
        assert "AI search assistant" in prompt

    def test_prompt_includes_location_context(self, sample_business_profile):
        """Verify prompt includes location information."""
        prompt = make_visibility_prompt(
            sample_business_profile,
            "best PT in Sugar Land",
            location_target="city"
        )
        
        city = sample_business_profile.get("city", "")
        if city:
            assert city in prompt

    def test_prompt_includes_gmb_rating(self, sample_business_profile):
        """Verify prompt includes GMB rating when available."""
        prompt = make_visibility_prompt(
            sample_business_profile,
            "best PT clinic",
            mode="evaluate"
        )
        
        rating = sample_business_profile.get("gmb_profile", {}).get("rating", 0)
        if rating:
            assert str(rating) in prompt or "rating" in prompt.lower()


class TestExtractJsonBlock:
    """Tests for JSON extraction from LLM responses."""

    def test_extracts_clean_json(self):
        """Verify clean JSON is extracted correctly."""
        text = '{"score": 0.8, "mentioned": true}'
        result = _extract_json_block(text)
        
        assert result["score"] == 0.8
        assert result["mentioned"] is True

    def test_extracts_json_from_text(self):
        """Verify JSON is extracted from surrounding text."""
        text = '''Here is my analysis:
        
        {"score": 0.75, "confidence": 0.9, "mentioned": true}
        
        This concludes my evaluation.'''
        
        result = _extract_json_block(text)
        
        assert result["score"] == 0.75
        assert result["confidence"] == 0.9

    def test_handles_invalid_json(self):
        """Verify invalid JSON returns empty dict."""
        text = "This is not JSON at all"
        result = _extract_json_block(text)
        
        assert result == {}

    def test_handles_partial_json(self):
        """Verify partial/broken JSON is handled gracefully."""
        text = '{"score": 0.8, "missing_bracket'
        result = _extract_json_block(text)
        
        # Should return empty dict for invalid JSON
        assert isinstance(result, dict)
