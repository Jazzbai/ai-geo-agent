"""Direct test of pipeline functions for bmcfamilymedicine.com"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.business_intelligence import create_business_profile, score_visibility

def test_bmcfamilymedicine():
    """Test the full pipeline directly for bmcfamilymedicine.com"""
    url = "https://bmcfamilymedicine.com"
    
    print("=" * 60)
    print(f"Testing Unified Pipeline for: {url}")
    print("=" * 60)
    print()
    
    try:
        # Step 1: Create business profile
        print("[Step 1] Creating business profile...")
        profile = create_business_profile(url)
        
        print("\n[OK] Profile Created:")
        print(f"  Name: {profile.get('business_name', 'N/A')}")
        print(f"  Website: {profile.get('website', 'N/A')}")
        print(f"  Domain: {profile.get('domain', 'N/A')}")
        print(f"  City: {profile.get('city', 'N/A')}")
        print(f"  Region: {profile.get('region', 'N/A')}")
        print(f"  Services Found: {len(profile.get('services', []))}")
        
        if profile.get('services'):
            print("\n  Services:")
            for svc in profile.get('services', [])[:5]:
                print(f"    - {svc.get('name', 'N/A')}")
        
        if profile.get('gmb_profile'):
            gmb = profile.get('gmb_profile', {})
            print(f"\n  GMB Profile:")
            print(f"    Rating: {gmb.get('rating', 'N/A')}")
            print(f"    Reviews: {gmb.get('reviews_count', 'N/A')}")
            print(f"    Categories: {', '.join(gmb.get('categories', [])[:3])}")
        
        # Step 2: Score visibility
        print("\n" + "=" * 60)
        print("[Step 2] Scoring visibility...")
        print("=" * 60)
        
        df = score_visibility(profile, model="gpt-4o-mini", max_queries=10)
        
        if df.empty:
            print("\n[WARNING] No visibility scores produced")
            return
        
        print(f"\n[OK] Visibility Scores Generated: {len(df)} queries")
        
        # Summary
        print("\nSummary:")
        print(f"  Total Queries: {len(df)}")
        print(f"  Avg Score: {df['score'].mean():.3f}")
        print(f"  Max Score: {df['score'].max():.3f}")
        print(f"  Min Score: {df['score'].min():.3f}")
        print(f"  Avg Visibility Index: {df['visibility_index'].mean():.2f}%")
        
        # Top scores
        print("\nTop Visibility Scores:")
        top_scores = df.nlargest(5, 'score')
        for i, (idx, row) in enumerate(top_scores.iterrows(), 1):
            print(f"\n  {i}. {row['query']}")
            print(f"     Score: {row['score']:.3f} | Visibility Index: {row['visibility_index']:.2f}%")
            print(f"     Rationale: {row['rationale'][:100]}...")
        
        print("\n" + "=" * 60)
        print("[SUCCESS] Pipeline completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR] Pipeline failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    test_bmcfamilymedicine()

