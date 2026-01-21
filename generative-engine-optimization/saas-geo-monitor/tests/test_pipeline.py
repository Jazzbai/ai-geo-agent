"""
Unit tests for the pipeline module.

Tests the summary building, report generation, and grading logic
without requiring external API calls.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.core.pipeline import _build_summary, _build_report, _compute_grade, _generate_recommendations


class TestGradeComputation:
    """Tests for visibility grade calculation."""

    @pytest.mark.parametrize("index,expected_grade", [
        (95, "A"),
        (80, "A"),
        (79, "B"),
        (60, "B"),
        (59, "C"),
        (40, "C"),
        (39, "D"),
        (20, "D"),
        (19, "F"),
        (0, "F"),
    ])
    def test_compute_grade_thresholds(self, index, expected_grade):
        """Verify grade thresholds are correctly applied."""
        assert _compute_grade(index) == expected_grade


class TestBuildSummary:
    """Tests for _build_summary function."""

    def test_empty_records_returns_defaults(self):
        """Verify empty records produce default summary values."""
        summary = _build_summary([], "Test Brand")
        
        assert summary["total_queries"] == 0
        assert summary["avg_score"] == 0.0
        assert summary["mention_rate"] == 0.0
        assert summary["visibility_index"] == 0.0

    def test_summary_calculates_avg_score(self, sample_visibility_record):
        """Verify average score is correctly calculated."""
        records = [
            {**sample_visibility_record, "score": 0.8},
            {**sample_visibility_record, "score": 0.6},
        ]
        
        summary = _build_summary(records, "Test Brand")
        
        assert summary["avg_score"] == pytest.approx(0.7, rel=0.01)

    def test_summary_calculates_mention_rate(self, sample_visibility_record):
        """Verify mention rate is correctly calculated."""
        records = [
            {**sample_visibility_record, "mentioned": True},
            {**sample_visibility_record, "mentioned": True},
            {**sample_visibility_record, "mentioned": False},
            {**sample_visibility_record, "mentioned": False},
        ]
        
        summary = _build_summary(records, "Test Brand")
        
        assert summary["mention_rate"] == pytest.approx(0.5, rel=0.01)

    def test_summary_tracks_competitor_mentions(self, sample_visibility_record):
        """Verify competitor mentions are tracked."""
        records = [
            {**sample_visibility_record, "competing_brands": ["Comp A", "Comp B"]},
            {**sample_visibility_record, "competing_brands": ["Comp A"]},
        ]
        
        summary = _build_summary(records, "Test Brand", competitors=["Comp A", "Comp B"])
        
        assert "competitor_mentions" in summary
        assert summary["competitor_mentions"].get("Comp A", 0) == 2

    def test_summary_counts_ai_citations(self, sample_visibility_record):
        """Verify AI citations are counted correctly."""
        records = [
            {**sample_visibility_record, "ai_citations": [{"source": "Yelp"}, {"source": "Google"}]},
            {**sample_visibility_record, "ai_citations": [{"source": "Healthgrades"}]},
        ]
        
        summary = _build_summary(records, "Test Brand")
        
        assert summary["ai_citations_total"] == 3


class TestBuildReport:
    """Tests for _build_report function."""

    def test_report_includes_grade(self, sample_business_profile, sample_visibility_record):
        """Verify report includes visibility grade."""
        records = [sample_visibility_record]
        summary = _build_summary(records, "Apex Physical Therapy")
        
        report = _build_report(sample_business_profile, records, summary)
        
        assert "visibility_grade" in report
        assert report["visibility_grade"] in ["A", "B", "C", "D", "F"]

    def test_report_includes_top_queries(self, sample_business_profile, sample_visibility_record):
        """Verify report includes top performing queries."""
        records = [
            {**sample_visibility_record, "query": "query 1", "score": 0.9},
            {**sample_visibility_record, "query": "query 2", "score": 0.7},
        ]
        summary = _build_summary(records, "Apex Physical Therapy")
        
        report = _build_report(sample_business_profile, records, summary)
        
        assert "top_queries" in report
        assert len(report["top_queries"]) > 0
        # First query should be highest score
        assert report["top_queries"][0]["score"] == 0.9

    def test_report_includes_recommendations(self, sample_business_profile, sample_visibility_record):
        """Verify report includes actionable recommendations."""
        records = [{**sample_visibility_record, "score": 0.2, "mentioned": False}]
        summary = _build_summary(records, "Test Brand")
        
        report = _build_report(sample_business_profile, records, summary)
        
        assert "recommendations" in report
        assert len(report["recommendations"]) > 0


class TestGenerateRecommendations:
    """Tests for recommendation generation logic."""

    def test_low_mention_rate_triggers_recommendation(self):
        """Verify low mention rate triggers visibility recommendation."""
        summary = {
            "mention_rate": 0.2,
            "brand_citation_rate": 0.5,
            "ai_citations_total": 10,
            "intent_coverage": {}
        }
        
        recommendations = _generate_recommendations(summary, [])
        
        assert any("visibility" in r.lower() for r in recommendations)

    def test_zero_citations_triggers_recommendation(self):
        """Verify zero AI citations triggers recommendation."""
        summary = {
            "mention_rate": 0.8,
            "brand_citation_rate": 0.5,
            "ai_citations_total": 0,
            "intent_coverage": {}
        }
        
        recommendations = _generate_recommendations(summary, [])
        
        assert any("citation" in r.lower() for r in recommendations)

    def test_good_metrics_get_positive_recommendation(self):
        """Verify good metrics produce positive feedback."""
        summary = {
            "mention_rate": 0.9,
            "brand_citation_rate": 0.8,
            "ai_citations_total": 50,
            "intent_coverage": {"best_in_class": 0.9, "local_search": 0.85}
        }
        
        recommendations = _generate_recommendations(summary, [])
        
        assert any("strong" in r.lower() or "maintain" in r.lower() for r in recommendations)
