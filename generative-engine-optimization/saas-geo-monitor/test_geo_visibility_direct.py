"""
Quick test script for geo visibility - tests using synchronous endpoint.

This script tests the 10 dental clinics using the synchronous /full-pipeline endpoint.
For async job queue testing, use test_async_geo_visibility.py instead.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.core.pipeline import run_full_pipeline
import json
from datetime import datetime

TEST_CLINICS = [
    {"url": "https://www.houstondentalcare.org/", "name": "Houston Dental Care"},
    {"url": "https://www.pearlshinedentalclinic.com/", "name": "Pearl Shine Dental"},
    {"url": "https://www.freshdentalcare.com/", "name": "Fresh Dental Care"},
    {"url": "https://www.utdentists.com/", "name": "UT Dentists"},
    {"url": "https://www.drfrazar.com/", "name": "Dr. Frazar"},
    {"url": "https://www.texasdentalcenter.com/", "name": "Texas Dental Center"},
    {"url": "https://www.nudentistrygardenoaks.com/", "name": "Nude Dentistry Garden Oaks"},
    {"url": "https://www.westhoustondental.com/", "name": "West Houston Dental"},
    {"url": "https://www.houstonuptowndentists.com/", "name": "Dr. Amanda Juarez"},
    {"url": "https://www.bellairedentalgroup.com/", "name": "Bellaire Dental Group"},
]


def test_clinic(url: str, name: str):
    """Test a single clinic."""
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"URL: {url}")
    print(f"{'='*80}")
    
    try:
        result = run_full_pipeline(
            url=url,
            model="gpt-4o-mini",
            max_queries=10,
            location_target="city"
        )
        
        summary = result.get("summary", {})
        print(f"\n✓ Success!")
        print(f"  Total Queries: {summary.get('total_queries', 0)}")
        print(f"  Avg Score: {summary.get('avg_score', 0):.2f}")
        print(f"  Max Score: {summary.get('max_score', 0):.2f}")
        print(f"  Min Score: {summary.get('min_score', 0):.2f}")
        print(f"  Avg Visibility Index: {summary.get('avg_visibility_index', 0):.2f}")
        
        return {"success": True, "name": name, "url": url, "result": result}
        
    except Exception as e:
        print(f"\n✗ Failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "name": name, "url": url, "error": str(e)}


def main():
    """Run tests for all clinics."""
    print("="*80)
    print("GEO VISIBILITY TEST - 10 DENTAL CLINICS")
    print("="*80)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Total clinics to test: {len(TEST_CLINICS)}\n")
    
    results = []
    for clinic in TEST_CLINICS:
        result = test_clinic(clinic["url"], clinic["name"])
        results.append(result)
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    succeeded = [r for r in results if r.get("success")]
    failed = [r for r in results if not r.get("success")]
    
    print(f"\nTotal: {len(results)}")
    print(f"✓ Succeeded: {len(succeeded)}")
    print(f"✗ Failed: {len(failed)}")
    
    if succeeded:
        print("\n" + "-"*80)
        print("SUCCESSFUL RESULTS")
        print("-"*80)
        for r in succeeded:
            summary = r.get("result", {}).get("summary", {})
            print(f"\n{r['name']}")
            print(f"  Avg Score: {summary.get('avg_score', 0):.2f}")
            print(f"  Queries: {summary.get('total_queries', 0)}")
    
    if failed:
        print("\n" + "-"*80)
        print("FAILED RESULTS")
        print("-"*80)
        for r in failed:
            print(f"\n{r['name']}: {r.get('error', 'Unknown error')}")
    
    # Save results
    output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ Results saved to: {output_file}")
    
    print(f"\nCompleted at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)


if __name__ == "__main__":
    main()

