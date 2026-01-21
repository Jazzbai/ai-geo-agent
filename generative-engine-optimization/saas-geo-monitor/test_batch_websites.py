"""
General batch testing script for multiple websites.
Processes a list of URLs through the business intelligence pipeline.
"""
import sys
import os
import json
import csv
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.business_intelligence import create_business_profile, score_visibility


def process_website(
    url: str,
    location_target: str = "city",
    max_queries: int = 10,
    save_profile: bool = True
) -> Dict[str, Any]:
    """
    Process a single website through the pipeline.
    
    Args:
        url: Website URL to process
        location_target: Location targeting mode ("city", "state", "nationwide", "general")
        max_queries: Maximum queries for visibility scoring
        save_profile: Whether to save individual profile JSON
    
    Returns:
        Dictionary with results
    """
    result = {
        "url": url,
        "status": "error",
        "timestamp": datetime.utcnow().isoformat(),
        "location_target": location_target,
        "profile": None,
        "visibility_scores": None,
        "error": None
    }
    
    try:
        # Step 1: Create business profile
        print(f"\n[Processing] {url}")
        print("-" * 80)
        
        profile = create_business_profile(url)
        result["profile"] = {
            "business_name": profile.get("business_name"),
            "domain": profile.get("domain"),
            "city": profile.get("city"),
            "state": profile.get("state"),
            "services_count": len(profile.get("services", [])),
            "gmb_rating": profile.get("gmb_profile", {}).get("rating"),
            "gmb_reviews": profile.get("gmb_profile", {}).get("reviews_count"),
        }
        
        # Save individual profile if requested
        if save_profile:
            safe_name = url.replace("https://", "").replace("http://", "").replace("/", "_").replace(":", "_")
            profile_file = f"results/profiles/{safe_name}_profile.json"
            os.makedirs(os.path.dirname(profile_file), exist_ok=True)
            with open(profile_file, 'w', encoding='utf-8') as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            result["profile_file"] = profile_file
        
        # Step 2: Score visibility
        print(f"  [Scoring] Visibility ({location_target})...")
        df = score_visibility(
            profile,
            model="gpt-4o-mini",
            max_queries=max_queries,
            location_target=location_target
        )
        
        if not df.empty:
            result["visibility_scores"] = {
                "total_queries": len(df),
                "avg_score": float(df["score"].mean()),
                "max_score": float(df["score"].max()),
                "min_score": float(df["score"].min()),
                "avg_visibility_index": float(df["visibility_index"].mean())
            }
            result["status"] = "success"
            print(f"  [Success] Avg Score: {result['visibility_scores']['avg_score']:.3f}, "
                  f"Visibility: {result['visibility_scores']['avg_visibility_index']:.2f}%")
        else:
            result["status"] = "warning"
            result["error"] = "No visibility scores generated"
            print(f"  [Warning] No visibility scores generated")
        
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
        print(f"  [Error] {str(e)}")
    
    return result


def process_batch(
    urls: List[str],
    location_target: str = "city",
    max_queries: int = 10,
    output_file: str = None
) -> List[Dict[str, Any]]:
    """
    Process a batch of websites.
    
    Args:
        urls: List of website URLs to process
        location_target: Location targeting mode
        max_queries: Maximum queries per website
        output_file: Optional CSV/JSON output file path
    
    Returns:
        List of result dictionaries
    """
    print("=" * 80)
    print(f"BATCH PROCESSING: {len(urls)} websites")
    print(f"Location Target: {location_target}")
    print(f"Max Queries per Site: {max_queries}")
    print("=" * 80)
    
    results = []
    total = len(urls)
    
    for idx, url in enumerate(urls, 1):
        print(f"\n[{idx}/{total}] Processing website...")
        result = process_website(url, location_target, max_queries, save_profile=False)
        results.append(result)
    
    # Summary
    print("\n" + "=" * 80)
    print("BATCH PROCESSING SUMMARY")
    print("=" * 80)
    
    success_count = sum(1 for r in results if r["status"] == "success")
    warning_count = sum(1 for r in results if r["status"] == "warning")
    error_count = sum(1 for r in results if r["status"] == "error")
    
    print(f"\nTotal Websites: {total}")
    print(f"  Success: {success_count}")
    print(f"  Warnings: {warning_count}")
    print(f"  Errors: {error_count}")
    
    # Average scores
    successful = [r for r in results if r["visibility_scores"]]
    if successful:
        avg_scores = [r["visibility_scores"]["avg_score"] for r in successful]
        avg_visibility = [r["visibility_scores"]["avg_visibility_index"] for r in successful]
        
        print(f"\nAverage Metrics (from {len(successful)} successful):")
        print(f"  Avg Score: {sum(avg_scores) / len(avg_scores):.3f}")
        print(f"  Avg Visibility Index: {sum(avg_visibility) / len(avg_visibility):.2f}%")
    
    # Save results
    if output_file:
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        
        if output_file.endswith('.csv'):
            # Save as CSV
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=[
                    'url', 'status', 'business_name', 'domain', 'city', 'state',
                    'services_count', 'gmb_rating', 'gmb_reviews',
                    'total_queries', 'avg_score', 'max_score', 'avg_visibility_index', 'error'
                ])
                writer.writeheader()
                for r in results:
                    row = {
                        'url': r['url'],
                        'status': r['status'],
                        'business_name': r['profile']['business_name'] if r['profile'] else '',
                        'domain': r['profile']['domain'] if r['profile'] else '',
                        'city': r['profile']['city'] if r['profile'] else '',
                        'state': r['profile']['state'] if r['profile'] else '',
                        'services_count': r['profile']['services_count'] if r['profile'] else 0,
                        'gmb_rating': r['profile']['gmb_rating'] if r['profile'] else '',
                        'gmb_reviews': r['profile']['gmb_reviews'] if r['profile'] else '',
                        'total_queries': r['visibility_scores']['total_queries'] if r['visibility_scores'] else 0,
                        'avg_score': r['visibility_scores']['avg_score'] if r['visibility_scores'] else 0.0,
                        'max_score': r['visibility_scores']['max_score'] if r['visibility_scores'] else 0.0,
                        'avg_visibility_index': r['visibility_scores']['avg_visibility_index'] if r['visibility_scores'] else 0.0,
                        'error': r['error'] or ''
                    }
                    writer.writerow(row)
        else:
            # Save as JSON
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_file}")
    
    return results


def load_urls_from_file(file_path: str) -> List[str]:
    """Load URLs from a text file (one URL per line)."""
    urls = []
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            url = line.strip()
            if url and not url.startswith('#'):  # Skip empty lines and comments
                # Ensure URL has protocol
                if not url.startswith(('http://', 'https://')):
                    url = f"https://{url}"
                urls.append(url)
    return urls


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch process websites for visibility scoring')
    parser.add_argument('urls', nargs='*', help='URLs to process (can also use --file)')
    parser.add_argument('--file', '-f', help='Text file with URLs (one per line)')
    parser.add_argument('--location-target', '-l', default='city', 
                       choices=['city', 'state', 'nationwide', 'general'],
                       help='Location targeting mode (default: city)')
    parser.add_argument('--max-queries', '-q', type=int, default=10,
                       help='Maximum queries per website (default: 10)')
    parser.add_argument('--output', '-o', help='Output file (CSV or JSON)')
    
    args = parser.parse_args()
    
    # Get URLs
    urls = []
    if args.file:
        urls.extend(load_urls_from_file(args.file))
    if args.urls:
        urls.extend([u if u.startswith(('http://', 'https://')) else f"https://{u}" for u in args.urls])
    
    if not urls:
        print("Error: No URLs provided. Use --file or provide URLs as arguments.")
        print("\nUsage examples:")
        print("  python test_batch_websites.py https://example.com https://example2.com")
        print("  python test_batch_websites.py --file urls.txt")
        print("  python test_batch_websites.py --file urls.txt --location-target state --output results.csv")
        sys.exit(1)
    
    # Process batch
    output_file = args.output or f"results/batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    results = process_batch(
        urls,
        location_target=args.location_target,
        max_queries=args.max_queries,
        output_file=output_file
    )

