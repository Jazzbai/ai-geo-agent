"""
Test script to check visibility for HVAC/Plumbing websites using async job queue.
"""
import requests
import time
import json
from typing import List, Dict, Any
from datetime import datetime
import concurrent.futures

# API base URL
API_BASE = "http://localhost:8000"

# Test data: 19 HVAC/Plumbing websites
TEST_WEBSITES = [
    {"url": "https://abacusplumbing.net", "name": "Abacus Plumbing"},
    {"url": "https://johnmooreservices.com", "name": "John Moore Services"},
    {"url": "https://villageplumbing.com", "name": "Village Plumbing"},
    {"url": "https://airteamltd.com", "name": "Air Team Ltd"},
    {"url": "https://richmondsair.com", "name": "Richmond's Air"},
    {"url": "https://coolithouston.com", "name": "Cool It Houston"},
    {"url": "https://missionac.com", "name": "Mission AC"},
    {"url": "https://springbranchac.com", "name": "Spring Branch AC"},
    {"url": "https://justfixittoday.com", "name": "Just Fix It Today"},
    {"url": "https://accomfort.us", "name": "AC Comfort"},
    {"url": "https://ars.com", "name": "ARS"},
    {"url": "https://airtron.com", "name": "Airtron"},
    {"url": "https://doctorcool.com", "name": "Doctor Cool"},
    {"url": "https://idealairservices.com", "name": "Ideal Air Services"},
    {"url": "https://htownacrepair.com", "name": "HTown AC Repair"},
    {"url": "https://aireserv.com", "name": "AireServ"},
    {"url": "https://americancomfortexperts.com", "name": "American Comfort Experts"},
    {"url": "https://coolcareac.com", "name": "Cool Care AC"},
    {"url": "https://houstonsmartair.com", "name": "Houston Smart Air"},
    {"url": "https://royalairhouston.com", "name": "Royal Air Houston"},
]


def submit_job(url: str, name: str) -> Dict[str, Any]:
    """Submit a single job to the queue."""
    payload = {
        "payload": {
            "url": url,
            "model": "gpt-4o-mini",
            "max_queries": 10,
            "location_target": "city"
        }
    }

    try:
        response = requests.post(
            f"{API_BASE}/api/v1/jobs/submit",
            json=payload,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        print(f"✓ Submitted: {name} (Job ID: {result['job_id'][:8]}...)")
        return result
    except Exception as e:
        print(f"✗ Failed to submit {name}: {e}")
        return None


def get_job_status(job_id: str) -> Dict[str, Any]:
    """Get the status of a job."""
    try:
        response = requests.get(
            f"{API_BASE}/api/v1/jobs/{job_id}",
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception:
        return None


def submit_all_jobs_parallel(websites: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Submit all jobs in parallel (non-blocking)."""
    print("\n" + "-"*80)
    print("STEP 1: SUBMITTING ALL JOBS IN PARALLEL")
    print("-"*80)
    print("Submitting all jobs simultaneously (non-blocking)...\n")

    submitted_jobs = []

    # Submit all jobs concurrently using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {
            executor.submit(submit_job, website["url"], website["name"]): website
            for website in websites
        }

        for future in concurrent.futures.as_completed(futures):
            website = futures[future]
            try:
                result = future.result()
                if result:
                    submitted_jobs.append({
                        "job_id": result["job_id"],
                        "name": website["name"],
                        "url": website["url"],
                        "submitted_at": time.time()
                    })
            except Exception as e:
                print(f"✗ Error submitting {website['name']}: {e}")

    print(f"\n✓ Submitted {len(submitted_jobs)} jobs successfully")
    print(f"  All jobs submitted in parallel - workers will process concurrently")
    return submitted_jobs


def monitor_all_jobs_parallel(submitted_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Monitor all jobs concurrently."""
    print("\n" + "-"*80)
    print("STEP 2: MONITORING JOB COMPLETION (PARALLEL PROCESSING)")
    print("-"*80)
    print("All jobs are being processed in parallel by Dramatiq workers...")
    print("Polling status every 5 seconds until all complete...\n")

    results = []
    remaining_jobs = submitted_jobs.copy()
    completed_job_ids = set()

    start_time = time.time()

    while remaining_jobs and (time.time() - start_time) < 1200:  # Max 20 minutes
        # Check all remaining jobs
        for job_info in remaining_jobs[:]:
            status = get_job_status(job_info["job_id"])
            if status:
                state = status.get("state")

                if state == "succeeded":
                    elapsed = time.time() - job_info["submitted_at"]
                    summary = status.get("result", {}).get("summary", {})
                    avg_score = summary.get("avg_score", 0)
                    print(f"✓ Completed: {job_info['name']} (took {elapsed:.1f}s, avg score: {avg_score:.2f})")
                    results.append(status)
                    completed_job_ids.add(job_info["job_id"])
                    remaining_jobs.remove(job_info)
                elif state == "failed":
                    error = status.get("error", "Unknown error")
                    elapsed = time.time() - job_info["submitted_at"]
                    print(f"✗ Failed: {job_info['name']} (took {elapsed:.1f}s) - {error}")
                    results.append(status)
                    completed_job_ids.add(job_info["job_id"])
                    remaining_jobs.remove(job_info)

        if remaining_jobs:
            in_progress = len([
                j for j in remaining_jobs 
                if get_job_status(j["job_id"]) and 
                get_job_status(j["job_id"]).get("state") == "running"
            ])
            queued = len(remaining_jobs) - in_progress
            print(f"  Status: {in_progress} running, {queued} queued, {len(results)} completed")
            time.sleep(5)

    # Get final status for any remaining jobs
    for job_info in remaining_jobs:
        final_status = get_job_status(job_info["job_id"])
        if final_status:
            results.append(final_status)

    total_time = time.time() - start_time
    print(f"\n✓ All jobs processed in {total_time:.1f} seconds")
    if submitted_jobs:
        print(f"  Average time per job: {total_time/len(submitted_jobs):.1f}s (parallel processing)")

    return results


def print_summary(results: List[Dict[str, Any]]):
    """Print a summary of all results."""
    print("\n" + "="*80)
    print("VISIBILITY ANALYSIS SUMMARY")
    print("="*80)

    succeeded = [r for r in results if r and r.get("state") == "succeeded"]
    failed = [r for r in results if r and r.get("state") == "failed"]
    incomplete = [r for r in results if not r or r.get("state") not in ["succeeded", "failed"]]

    print(f"\nTotal Jobs: {len(results)}")
    print(f"✓ Succeeded: {len(succeeded)}")
    print(f"✗ Failed: {len(failed)}")
    print(f"⚠ Incomplete: {len(incomplete)}")

    if succeeded:
        print("\n" + "-"*80)
        print("SUCCESSFUL RESULTS (Ranked by Average Visibility Score)")
        print("-"*80)
        
        # Sort by average score descending
        sorted_results = sorted(
            succeeded,
            key=lambda r: r.get("result", {}).get("summary", {}).get("avg_score", 0),
            reverse=True
        )
        
        for idx, result in enumerate(sorted_results, 1):
            job_data = result.get("result", {})
            summary = job_data.get("summary", {})
            profile = job_data.get("profile", {})
            
            print(f"\n#{idx} - {result.get('job_id', 'N/A')[:8]}...")
            print(f"  Business: {profile.get('business_name', 'N/A')}")
            print(f"  URL: {profile.get('website_url', 'N/A')}")
            print(f"  Total Queries: {summary.get('total_queries', 0)}")
            print(f"  Avg Score: {summary.get('avg_score', 0):.3f}")
            print(f"  Max Score: {summary.get('max_score', 0):.3f}")
            print(f"  Min Score: {summary.get('min_score', 0):.3f}")
            print(f"  Avg Visibility Index: {summary.get('avg_visibility_index', 0):.3f}")

    if failed:
        print("\n" + "-"*80)
        print("FAILED RESULTS")
        print("-"*80)
        for result in failed:
            print(f"\nJob ID: {result.get('job_id', 'N/A')}")
            print(f"  Error: {result.get('error', 'Unknown error')}")

    # Save results to JSON file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"visibility_results_hvac_plumbing_{timestamp}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ Results saved to: {output_file}")


def main():
    """Main test function."""
    print("="*80)
    print("HVAC/PLUMBING VISIBILITY ANALYSIS - ASYNC JOB QUEUE TEST")
    print("="*80)
    print(f"\nTesting {len(TEST_WEBSITES)} HVAC/Plumbing websites")
    print(f"API Base URL: {API_BASE}")
    print(f"\nProcessing Mode: PARALLEL (all jobs submitted simultaneously)")
    print(f"Workers will process multiple jobs concurrently\n")

    # Check if API is running
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        if response.status_code != 200:
            print("⚠ Warning: API health check returned non-200 status")
    except Exception as e:
        print(f"✗ ERROR: Cannot connect to API at {API_BASE}")
        print(f"  Please ensure the API server is running:")
        print(f"  uvicorn app.main:app --host 0.0.0.0 --port 8000")
        print(f"\n  And ensure Dramatiq workers are running:")
        print(f"  dramatiq app.workers.geo_tasks:run_geo_job --processes 2 --threads 4")
        return

    # Step 1: Submit all jobs in parallel
    submitted_jobs = submit_all_jobs_parallel(TEST_WEBSITES)

    if not submitted_jobs:
        print("\n✗ No jobs were submitted successfully. Check API server connection.")
        return

    # Step 2: Monitor all jobs (they process in parallel)
    results = monitor_all_jobs_parallel(submitted_jobs)

    # Step 3: Print summary
    print_summary(results)

    print("\n" + "="*80)
    print("TEST COMPLETE")
    print("="*80)
    print("\nNote: With parallel processing, multiple jobs run simultaneously.")
    print("Total time is much shorter than sequential processing!")


if __name__ == "__main__":
    main()

