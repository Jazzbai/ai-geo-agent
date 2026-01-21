"""
Test script for async geo visibility job queue system.

Tests the Dramatiq-based job queue by submitting multiple dental clinic websites
and monitoring their processing status.
"""
import requests
import time
import json
from typing import List, Dict, Any

# API base URL
API_BASE = "http://localhost:8000"

# Test data: 10 dental clinics
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
    except Exception as e:
        print(f"✗ Failed to get status for {job_id}: {e}")
        return None


def wait_for_completion(job_id: str, name: str, max_wait: int = 300) -> Dict[str, Any]:
    """Wait for a job to complete, polling every 5 seconds."""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        status = get_job_status(job_id)
        if not status:
            return None
        
        state = status.get("state")
        print(f"  [{name}] Status: {state}")
        
        if state == "succeeded":
            print(f"✓ Completed: {name}")
            return status
        elif state == "failed":
            error = status.get("error", "Unknown error")
            print(f"✗ Failed: {name} - {error}")
            return status
        
        # Wait before next poll
        time.sleep(5)
    
    print(f"⚠ Timeout: {name} (exceeded {max_wait}s)")
    return None


def print_summary(results: List[Dict[str, Any]]):
    """Print a summary of all results."""
    print("\n" + "="*80)
    print("TEST SUMMARY")
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
        print("SUCCESSFUL RESULTS")
        print("-"*80)
        for result in succeeded:
            job_data = result.get("result", {})
            summary = job_data.get("summary", {})
            print(f"\nJob ID: {result.get('job_id', 'N/A')}")
            print(f"  Total Queries: {summary.get('total_queries', 0)}")
            print(f"  Avg Score: {summary.get('avg_score', 0):.2f}")
            print(f"  Avg Visibility Index: {summary.get('avg_visibility_index', 0):.2f}")
    
    if failed:
        print("\n" + "-"*80)
        print("FAILED RESULTS")
        print("-"*80)
        for result in failed:
            print(f"\nJob ID: {result.get('job_id', 'N/A')}")
            print(f"  Error: {result.get('error', 'Unknown error')}")
    
    # Save results to JSON file
    output_file = "test_geo_visibility_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n✓ Results saved to: {output_file}")


def submit_all_jobs_parallel(clinics: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Submit all jobs in parallel (non-blocking)."""
    import concurrent.futures
    
    print("\n" + "-"*80)
    print("STEP 1: SUBMITTING ALL JOBS IN PARALLEL")
    print("-"*80)
    print("Submitting all jobs simultaneously (non-blocking)...\n")
    
    submitted_jobs = []
    
    # Submit all jobs concurrently using ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(submit_job, clinic["url"], clinic["name"]): clinic
            for clinic in clinics
        }
        
        for future in concurrent.futures.as_completed(futures):
            clinic = futures[future]
            try:
                result = future.result()
                if result:
                    submitted_jobs.append({
                        "job_id": result["job_id"],
                        "name": clinic["name"],
                        "url": clinic["url"],
                        "submitted_at": time.time()
                    })
            except Exception as e:
                print(f"✗ Error submitting {clinic['name']}: {e}")
    
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
    
    while remaining_jobs and (time.time() - start_time) < 600:  # Max 10 minutes
        # Check all remaining jobs
        for job_info in remaining_jobs[:]:
            status = get_job_status(job_info["job_id"])
            if status:
                state = status.get("state")
                
                if state == "succeeded":
                    elapsed = time.time() - job_info["submitted_at"]
                    print(f"✓ Completed: {job_info['name']} (took {elapsed:.1f}s)")
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
            in_progress = len([j for j in remaining_jobs if get_job_status(j["job_id"]) and get_job_status(j["job_id"]).get("state") == "running"])
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
    print(f"  Average time per job: {total_time/len(submitted_jobs):.1f}s (parallel processing)")
    
    return results


def main():
    """Main test function."""
    print("="*80)
    print("GEO VISIBILITY ASYNC JOB QUEUE TEST - PARALLEL PROCESSING")
    print("="*80)
    print(f"\nTesting {len(TEST_CLINICS)} dental clinics")
    print(f"API Base URL: {API_BASE}")
    print(f"\nProcessing Mode: PARALLEL (all jobs submitted simultaneously)")
    print(f"Workers will process multiple jobs concurrently\n")
    
    # Step 1: Submit all jobs in parallel
    submitted_jobs = submit_all_jobs_parallel(TEST_CLINICS)
    
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

