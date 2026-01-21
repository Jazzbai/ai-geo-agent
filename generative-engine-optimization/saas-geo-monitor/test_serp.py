#!/usr/bin/env python3
"""Quick test of SERP grounding module."""
import asyncio
import sys
sys.path.insert(0, '/app')

from app.core.serp_grounding import fetch_serp_snippets, detect_brand_in_snippets

async def main():
    print("Testing SERP grounding...")
    query = "best physical therapy houston"
    location = "Houston TX"
    
    snippets = await fetch_serp_snippets(query, location, num_results=5)
    print(f"\nGot {len(snippets)} snippets for: {query}")
    
    for s in snippets:
        print(f"\n[{s.get('position')}] {s.get('title', '')[:60]}")
        print(f"    URL: {s.get('url', '')[:80]}")
        print(f"    Snippet: {s.get('snippet', '')[:100]}...")
    
    # Test brand detection
    if snippets:
        evidence = detect_brand_in_snippets(snippets, "Apex Rehab", "apexrehab.com")
        print(f"\nBrand detection for 'Apex Rehab': {evidence}")

if __name__ == "__main__":
    asyncio.run(main())

