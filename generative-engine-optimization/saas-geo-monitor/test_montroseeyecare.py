\"\"\"
Test script for Montrose Eye Care business intelligence pipeline.
\"\"\"
import sys
import os
import json
from pathlib import Path

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.business_intelligence import create_business_profile, score_visibility

def test_montroseeyecare():
    \"\"\"Test the full pipeline for montroseeyecarehtx.com\"\"\"
    url = \"https://www.montroseeyecarehtx.com/\"
    
    print(\"=\" * 70)
    print(\"Testing Montrose Eye Care Business Intelligence Pipeline\")
    print(\"=\" * 70)
    print(f\"\\nWebsite: {url}\\n\")
    
    # Step 1: Create business profile
    print(\"Step 1: Creating business profile...\")
    print(\"-\" * 70)
    try:
        profile = create_business_profile(url)
        
        print(f\"\\n✓ Business Profile Created:\")
        print(f\"  Business Name: {profile.get('business_name', 'N/A')}\")
        print(f\"  Website: {profile.get('website', 'N/A')}\")
        print(f\"  Domain: {profile.get('domain', 'N/A')}\")
        
        if profile.get('city'):
            print(f\"  Location: {profile.get('city')}, {profile.get('region', '')} {profile.get('postal_code', '')}\")
        
        if profile.get('about_us') and profile['about_us'] != \"Not found.\":
            about_preview = profile['about_us'][:200] + \"...\" if len(profile['about_us']) > 200 else profile['about_us']
            print(f\"  About: {about_preview}\")
        
        services = profile.get('services', [])
        if services:
            print(f\"\\n  Services ({len(services)} found):\")
            for i, service in enumerate(services[:5], 1):
                if isinstance(service, dict):
                    print(f\"    {i}. {service.get('name', 'N/A')}\")
                else:
                    print(f\"    {i}. {service}\")
        
        # GMB Profile
        gmb = profile.get('gmb_profile', {})
        if gmb.get('place_id'):
            print(f\"\\n✓ Google My Business Profile:\")
            print(f\"  Place ID: {gmb.get('place_id')}\")
            print(f\"  Name: {gmb.get('name', 'N/A')}\")
            print(f\"  Rating: {gmb.get('rating', 0)} ({gmb.get('reviews_count', 0)} reviews)\")
            print(f\"  Address: {gmb.get('address', 'N/A')}\")
            if gmb.get('phone'):
                print(f\"  Phone: {gmb.get('phone')}\")
            if gmb.get('categories'):
                print(f\"  Categories: {', '.join(gmb.get('categories', [])[:3])}\")
        
        # Step 2: Score visibility
        print(\"\\n\" + \"=\" * 70)
        print(\"Step 2: Scoring AI Search Visibility...\")
        print(\"-\" * 70)
        
        visibility_df = score_visibility(profile, model=\"gpt-4o-mini\", max_queries=10)
        
        if not visibility_df.empty:
            print(f\"\\n✓ Visibility Scores Generated ({len(visibility_df)} queries):\")
            print(f\"\\n  Summary:\")
            print(f\"    Average Score: {visibility_df['score'].mean():.3f}\")
            print(f\"    Max Score: {visibility_df['score'].max():.3f}\")
            print(f\"    Min Score: {visibility_df['score'].min():.3f}\")
            print(f\"    Average Visibility Index: {visibility_df['visibility_index'].mean():.1f}%\")
            
            print(f\"\\n  Top 5 Queries:\")
            top_queries = visibility_df.nlargest(5, 'score')
            for idx, row in top_queries.iterrows():
                print(f\"    - {row['query']}\")
                print(f\"      Score: {row['score']:.3f} | Visibility: {row['visibility_index']:.1f}%\")
                if row.get('rationale'):
                    rationale_preview = row['rationale'][:100] + \"...\" if len(row['rationale']) > 100 else row['rationale']
                    print(f\"      Rationale: {rationale_preview}\")
        else:
            print(\"\\n⚠ No visibility scores generated\")
        
        # Step 3: Save results
        print(\"\\n\" + \"=\" * 70)
        print(\"Step 3: Saving Results...\")
        print(\"-\" * 70)
        
        output_file = \"montroseeyecare_results.json\"
        results = {
            \"url\": url,
            \"profile\": profile,
            \"visibility_scores\": visibility_df.to_dict('records') if not visibility_df.empty else [],
            \"summary\": {
                \"total_queries\": len(visibility_df),
                \"avg_score\": float(visibility_df[\"score\"].mean()) if not visibility_df.empty else 0,
                \"max_score\": float(visibility_df[\"score\"].max()) if not visibility_df.empty else 0,
                \"min_score\": float(visibility_df[\"score\"].min()) if not visibility_df.empty else 0,
                \"avg_visibility_index\": float(visibility_df[\"visibility_index\"].mean()) if not visibility_df.empty else 0
            }
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f\"\\n✓ Results saved to: {output_file}\")
        
        print(\"\\n\" + \"=\" * 70)
        print(\"Test Complete!\")
        print(\"=\" * 70)
        
        return results
        
    except Exception as e:
        print(f\"\\n✗ Error: {e}\")
        import traceback
        traceback.print_exc()
        return None


if __name__ == \"__main__\":
    test_montroseeyecare()
