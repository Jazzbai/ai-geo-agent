"""
Quick test script to check business visibility.
Run: python test_visibility.py <website_url>
"""
import sys
import requests
import json
import os

# Fix Windows console encoding
if sys.platform == 'win32':
    os.system('chcp 65001 >nul 2>&1')

API_BASE = "http://localhost:8000"

def test_visibility(url: str, max_queries: int = 5):
    """Test visibility for a business website."""
    print(f"\n{'='*60}")
    print(f"Testing Visibility for: {url}")
    print(f"{'='*60}\n")
    
    payload = {
        "url": url,
        "model": "gpt-4o-mini",
        "max_queries": max_queries,
        "location_target": "city",
        "mode": "evaluate"
    }
    
    print("Sending request to API...")
    print(f"   Payload: {json.dumps(payload, indent=2)}\n")
    
    try:
        response = requests.post(
            f"{API_BASE}/api/v1/geo/full-pipeline",
            json=payload,
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code != 200:
            print(f"ERROR: HTTP {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        data = response.json()
        
        # Display results
        print("Analysis Complete!\n")
        print(f"{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        
        summary = data.get("summary", {})
        report = data.get("report", {})
        
        print(f"\nBusiness: {summary.get('brand', 'Unknown')}")
        print(f"Visibility Index: {summary.get('visibility_index', 0):.1f}%")
        print(f"Grade: {report.get('visibility_grade', 'N/A')}")
        print(f"Mention Rate: {summary.get('mention_rate', 0)*100:.1f}%")
        print(f"Brand Citation Rate: {summary.get('brand_citation_rate', 0)*100:.1f}%")
        print(f"Total Queries: {summary.get('total_queries', 0)}")
        print(f"AI Citations: {summary.get('ai_citations_total', 0)}")
        
        # Query results
        visibility_scores = data.get("visibility_scores", [])
        if visibility_scores:
            print(f"\n{'='*60}")
            print("QUERY RESULTS")
            print(f"{'='*60}\n")
            
            for i, score in enumerate(visibility_scores[:10], 1):
                status = "[OK]" if score.get("mentioned") else "[NO]"
                print(f"{i}. {status} {score.get('query', 'N/A')}")
                print(f"   Score: {score.get('score', 0)*100:.1f}% | "
                      f"Confidence: {score.get('confidence', 0)*100:.1f}%")
                if score.get("rationale"):
                    print(f"   Note: {score['rationale'][:100]}...")
                print()
        
        # Competitor comparison
        if report.get("competitor_comparison"):
            print(f"\n{'='*60}")
            print("COMPETITOR COMPARISON")
            print(f"{'='*60}\n")
            
            for comp, comp_data in report["competitor_comparison"].items():
                rate = comp_data.get("mention_rate", 0) * 100
                count = comp_data.get("mention_count", 0)
                print(f"  - {comp}: {rate:.1f}% ({count} mentions)")
        
        # Recommendations
        recommendations = report.get("recommendations", [])
        if recommendations:
            print(f"\n{'='*60}")
            print("RECOMMENDATIONS")
            print(f"{'='*60}\n")
            
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. {rec}")
        
        print(f"\n{'='*60}")
        print("Test Complete!")
        print(f"{'='*60}\n")
        
    except requests.exceptions.Timeout:
        print("Request timed out. The analysis may take longer than expected.")
    except requests.exceptions.ConnectionError:
        print("Connection error. Make sure Docker containers are running:")
        print("   docker-compose ps")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_visibility.py <website_url> [max_queries]")
        print("\nExample:")
        print("  python test_visibility.py https://example.com")
        print("  python test_visibility.py https://example.com 10")
        sys.exit(1)
    
    url = sys.argv[1]
    max_queries = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    test_visibility(url, max_queries)
