"""
Test script for Reliant Energy business intelligence pipeline.
Tests the full pipeline: crawl → profile → GMB data → visibility scoring.
"""
import sys
import os
import json
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.business_intelligence import create_business_profile, score_visibility

def test_reliant_energy():
    """Test Reliant Energy website with full pipeline."""
    url = "https://www.reliant.com/"
    
    print("=" * 80)
    print("RELiant ENERGY - Business Intelligence Pipeline Test")
    print("=" * 80)
    print()
    
    # Step 1: Create business profile
    print("Step 1: Creating business profile from website...")
    print(f"URL: {url}")
    print()
    
    try:
        profile = create_business_profile(url)
        print("Profile created successfully!")
        print()
        print("Business Profile Summary:")
        print("-" * 80)
        print(f"Business Name: {profile.get('business_name', 'N/A')}")
        print(f"Services: {len(profile.get('services', []))} services found")
        print(f"City: {profile.get('city', 'N/A')}")
        print(f"State: {profile.get('state', 'N/A')}")
        print(f"GMB Rating: {profile.get('gmb_profile', {}).get('rating', 'N/A')}")
        print()
        
        # Show GMB data if available
        gmb_profile = profile.get('gmb_profile', {})
        if gmb_profile and gmb_profile.get('address') != 'Not found':
            print("Google My Business Data:")
            print(f"  Address: {gmb_profile.get('address', 'N/A')}")
            print(f"  Rating: {gmb_profile.get('rating', 'N/A')}/5")
            print(f"  Reviews: {gmb_profile.get('reviews_count', 'N/A')}")
            print(f"  Categories: {', '.join(gmb_profile.get('categories', [])[:5])}")
            print()
        
        # Step 2: Test visibility scoring with different location targets
        print("Step 2: Testing visibility scoring...")
        print("=" * 80)
        print()
        
        location_targets = ["city", "state", "nationwide", "general"]
        
        for location_target in location_targets:
            print(f"\nTesting with location_target: '{location_target}'")
            print("-" * 80)
            
            try:
                df = score_visibility(
                    profile,
                    model="gpt-4o-mini",
                    max_queries=10,
                    location_target=location_target
                )
                
                if df.empty:
                    print(f"  No scores generated for '{location_target}'")
                    continue
                
                # Show summary
                avg_score = df["score"].mean()
                max_score = df["score"].max()
                avg_visibility = df["visibility_index"].mean()
                
                print(f"  Results Summary:")
                print(f"    Total Queries: {len(df)}")
                print(f"    Average Score: {avg_score:.3f}")
                print(f"    Max Score: {max_score:.3f}")
                print(f"    Average Visibility Index: {avg_visibility:.2f}%")
                print()
                
                # Show top 3 queries by score
                top_queries = df.nlargest(3, 'score')[['query', 'score', 'rationale']]
                print(f"  Top 3 Queries by Visibility Score:")
                for idx, row in top_queries.iterrows():
                    print(f"    Query: {row['query']}")
                    print(f"    Score: {row['score']:.3f}")
                    print(f"    Rationale: {row['rationale'][:100]}...")
                    print()
                
            except Exception as e:
                print(f"  Error testing '{location_target}': {str(e)}")
                import traceback
                traceback.print_exc()
        
        print()
        print("=" * 80)
        print("TEST COMPLETE")
        print("=" * 80)
        
        # Save full profile to JSON for inspection
        output_file = "test_reliant_profile.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(profile, f, indent=2, ensure_ascii=False)
        print(f"\nFull profile saved to: {output_file}")
        
    except Exception as e:
        print(f"ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_reliant_energy()

