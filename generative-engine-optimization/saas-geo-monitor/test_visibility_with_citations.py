"""
Enhanced visibility checker with automated prompt engineering and citation tracking.
Checks where AI models (ChatGPT, Perplexity, Gemini) get their data from.
"""
import sys
import os
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from urllib.parse import urlparse
import httpx

# Fix Windows console encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Add app directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.business_intelligence import (
    create_business_profile, 
    generate_queries, 
    score_visibility
)
from app.core.prompt_engineer import PromptEngineer

# Try to import citation search providers
try:
    import sys as sys_mod
    _geo_path = os.path.join(os.path.dirname(__file__), "..", "..", "geo-visibility-engine")
    if os.path.exists(_geo_path) and _geo_path not in sys_mod.path:
        sys_mod.path.insert(0, _geo_path)
    
    from providers import openai_search, perplexity_search, gemini_search
    from schemas import Area
    HAVE_CITATION_PROVIDERS = True
except Exception:
    HAVE_CITATION_PROVIDERS = False
    print("Warning: Citation providers not available. Using basic search.")


async def search_with_citations(
    query: str,
    business_name: str,
    domain: str,
    providers: List[str] = ["openai", "perplexity"],
    city: str = "",
    state: str = ""
) -> Dict[str, Any]:
    """
    Search with multiple AI providers to find citations.
    
    Args:
        query: Search query
        business_name: Business name to check for
        domain: Business domain to check for
        providers: List of providers to use
        city: City name for location context
        state: State name for location context
    
    Returns:
        Dictionary with citations and presence data
    """
    results = {
        "query": query,
        "citations": {},
        "business_found": {},
        "citation_sources": []
    }
    
    if not HAVE_CITATION_PROVIDERS:
        # Fallback: Use OpenAI API directly
        return await _simple_citation_search(query, business_name, domain)
    
    # Create area object if we have location
    area = None
    if city and state:
        area = Area(name=city, admin=state, country="US", lat=0.0, lon=0.0)
    elif city:
        area = Area(name=city, admin="", country="US", lat=0.0, lon=0.0)
    else:
        area = Area(name="", admin="", country="US", lat=0.0, lon=0.0)
    
    tasks = []
    
    if "openai" in providers:
        try:
            tasks.append(
                openai_search.ai_visibility_search(query, area, business_name, domain)
            )
        except Exception as e:
            print(f"  OpenAI search error: {e}")
    
    if "perplexity" in providers:
        try:
            tasks.append(
                perplexity_search.ai_visibility_search(query, area, business_name, domain)
            )
        except Exception as e:
            print(f"  Perplexity search error: {e}")
    
    if "gemini" in providers:
        try:
            tasks.append(
                gemini_search.ai_visibility_search(query, area, business_name, domain)
            )
        except Exception as e:
            print(f"  Gemini search error: {e}")
    
    if tasks:
        search_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for idx, result in enumerate(search_results):
            if isinstance(result, Exception):
                continue
            
            provider = result.provider if hasattr(result, 'provider') else f"provider_{idx}"
            citations = result.citations if hasattr(result, 'citations') else []
            presence = result.answer_presence if hasattr(result, 'answer_presence') else False
            
            results["citations"][provider] = citations
            results["business_found"][provider] = presence
            
            # Track all citation sources
            for citation in citations:
                if citation not in results["citation_sources"]:
                    results["citation_sources"].append(citation)
    
    return results


async def _simple_citation_search(
    query: str,
    business_name: str,
    domain: str
) -> Dict[str, Any]:
    """Fallback citation search using OpenAI API directly."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "query": query,
            "citations": {},
            "business_found": {},
            "citation_sources": [],
            "error": "OPENAI_API_KEY not set"
        }
    
    prompt = f"""For the query: "{query}"

Find top recommendations and provide sources/citations. 
Return as JSON with format:
{{"items": [{{"name": "...", "url": "...", "why": "..."}}]}}

Check if "{business_name}" ({domain}) appears in the results."""

    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            data = r.json()
        
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        items = parsed.get("items", [])
        
        citations = []
        business_found = False
        for item in items:
            url_str = item.get("url", "").lower()
            name = item.get("name", "").lower()
            if url_str:
                citations.append(url_str)
            if domain.lower() in url_str or business_name.lower() in name:
                business_found = True
        
        return {
            "query": query,
            "citations": {"openai": citations},
            "business_found": {"openai": business_found},
            "citation_sources": citations
        }
    except Exception as e:
        return {
            "query": query,
            "citations": {},
            "business_found": {},
            "citation_sources": [],
            "error": str(e)
        }


def auto_generate_prompts(
    profile: Dict[str, Any],
    location_target: str = "city"
) -> List[Dict[str, Any]]:
    """
    Automatically generate optimized prompts based on business profile.
    
    Returns:
        List of prompt configurations with query templates
    """
    business_name = profile.get("business_name") or profile.get("name", "")
    services = profile.get("services", [])
    city = profile.get("city", "")
    state = profile.get("state", "")
    
    # Generate base queries
    queries = generate_queries(profile, max_per_intent=3, location_target=location_target)
    
    prompt_configs = []
    for query in queries[:10]:  # Limit to top 10 queries
        config = {
            "query": query,
            "prompt_variant": "standard",
            "location_context": f"{city}, {state}" if city and state else (city or state or "general"),
            "services": [s.get("name") if isinstance(s, dict) else str(s) for s in services[:3]]
        }
        prompt_configs.append(config)
    
    return prompt_configs


async def check_visibility_with_citations(
    url: str,
    location_target: str = "city",
    max_queries: int = 10,
    providers: List[str] = ["openai", "perplexity"],
    firecrawl_key: str = None,
    qdrant_url: str = None,
    qdrant_key: str = None,
    goal: str = "visibility_check"
) -> Dict[str, Any]:
    """
    Complete visibility check with citation tracking.
    
    Args:
        url: Website URL to check
        location_target: Location targeting mode
        max_queries: Maximum queries to test
        providers: AI providers to check (openai, perplexity, gemini)
    
    Returns:
        Complete visibility analysis with citations
    """
    print(f"\n{'='*80}")
    print(f"VISIBILITY CHECK WITH CITATIONS")
    print(f"{'='*80}")
    print(f"URL: {url}")
    print(f"Location Target: {location_target}")
    print(f"Providers: {', '.join(providers)}")
    print()
    
    # Step 1: Create business profile and crawl website
    print("[Step 1] Creating business profile and crawling website...")
    profile = create_business_profile(url)
    business_name = profile.get("business_name") or profile.get("name", "")
    domain = urlparse(url).netloc.replace("www.", "")
    
    # Get website content for knowledge base
    from app.core.business_intelligence import crawl_website
    
    # Set Firecrawl key if provided
    if firecrawl_key:
        os.environ['FIRECRAWL_API_KEY'] = firecrawl_key
    
    website_content = crawl_website(url)
    
    print(f"  Business: {business_name}")
    print(f"  Domain: {domain}")
    print(f"  Location: {profile.get('city', 'N/A')}, {profile.get('state', 'N/A')}")
    print(f"  Pages crawled: {len(website_content)}")
    print()
    
    # Step 2: Intelligent prompt engineering with knowledge base
    print("[Step 2] Intelligent prompt engineering with knowledge base...")
    print("  Using AI-powered prompt engineering system...")
    print("  Building knowledge base from website data...")
    
    try:
        engineer = PromptEngineer(qdrant_url=qdrant_url, qdrant_api_key=qdrant_key)
        workflow = engineer.create_complete_prompt_workflow(
            profile,
            goal=goal,
            location_target=location_target,
            max_queries=max_queries,
            website_content=website_content
        )
        
        queries = [q["query"] for q in workflow["queries"]]
        domain_info = workflow["domain_analysis"]
        
        print(f"  Domain: {domain_info.get('industry_category', 'N/A')}")
        print(f"  Business Type: {domain_info.get('business_type', 'N/A')}")
        print(f"  Target Audience: {domain_info.get('target_audience', 'N/A')}")
        print(f"  Generated {len(queries)} intelligent queries")
        print()
        
        # Store workflow for later use
        profile["_prompt_workflow"] = workflow
        
    except Exception as e:
        print(f"  Warning: Intelligent prompt engineering failed: {e}")
        print("  Falling back to basic prompt generation...")
        prompt_configs = auto_generate_prompts(profile, location_target)
        queries = [cfg["query"] for cfg in prompt_configs[:max_queries]]
        print(f"  Generated {len(queries)} basic query prompts")
        print()
    
    # Step 3: Check citations for each query
    print("[Step 3] Checking citations across AI providers...")
    print("-" * 80)
    
    citation_results = []
    for idx, query in enumerate(queries, 1):
        print(f"  [{idx}/{len(queries)}] Query: {query}")
        
        citation_data = await search_with_citations(
            query=query,
            business_name=business_name,
            domain=domain,
            providers=providers,
            city=profile.get("city", ""),
            state=profile.get("state", "")
        )
        
        citation_results.append(citation_data)
        
        # Show quick results
        found_in = [p for p, found in citation_data.get("business_found", {}).items() if found]
        if found_in:
            print(f"    [FOUND] in: {', '.join(found_in)}")
        else:
            print(f"    [NOT FOUND] in any provider")
        
        if citation_data.get("citation_sources"):
            print(f"    Citations: {len(citation_data['citation_sources'])} sources found")
    
    print()
    
    # Step 4: Calculate visibility scores
    print("[Step 4] Calculating visibility scores...")
    df = score_visibility(
        profile,
        model="gpt-4o-mini",
        max_queries=max_queries,
        location_target=location_target
    )
    
    # Step 5: Combine results
    combined_results = {
        "url": url,
        "timestamp": datetime.utcnow().isoformat(),
        "business_profile": {
            "name": business_name,
            "domain": domain,
            "city": profile.get("city"),
            "state": profile.get("state"),
            "services_count": len(profile.get("services", [])),
            "gmb_rating": profile.get("gmb_profile", {}).get("rating"),
        },
        "visibility_scores": df.to_dict('records') if not df.empty else [],
        "citation_analysis": {
            "total_queries_checked": len(citation_results),
            "providers_checked": providers,
            "queries_with_citations": sum(1 for r in citation_results if r.get("citation_sources")),
            "queries_found_in": sum(1 for r in citation_results if any(r.get("business_found", {}).values())),
            "total_citation_sources": len(set(
                cit for r in citation_results 
                for cit in r.get("citation_sources", [])
            )),
            "provider_breakdown": {}
        },
        "detailed_citations": citation_results
    }
    
    # Provider breakdown
    for provider in providers:
        found_count = sum(
            1 for r in citation_results 
            if r.get("business_found", {}).get(provider, False)
        )
        combined_results["citation_analysis"]["provider_breakdown"][provider] = {
            "found_in": found_count,
            "total_queries": len(citation_results),
            "success_rate": found_count / len(citation_results) if citation_results else 0.0
        }
    
    # Summary
    print("\n" + "="*80)
    print("RESULTS SUMMARY")
    print("="*80)
    print(f"Total Queries Tested: {len(citation_results)}")
    print(f"Queries with Citations: {combined_results['citation_analysis']['queries_with_citations']}")
    print(f"Queries Where Business Found: {combined_results['citation_analysis']['queries_found_in']}")
    print(f"\nProvider Success Rates:")
    for provider, data in combined_results["citation_analysis"]["provider_breakdown"].items():
        print(f"  {provider}: {data['found_in']}/{data['total_queries']} "
              f"({data['success_rate']*100:.1f}%)")
    
    if not df.empty:
        print(f"\nVisibility Scores:")
        print(f"  Average Score: {df['score'].mean():.3f}")
        print(f"  Average Visibility Index: {df['visibility_index'].mean():.2f}%")
        print(f"  Max Score: {df['score'].max():.3f}")
    
    return combined_results


def analyze_competitors_and_generate_report(
    results: Dict[str, Any],
    output_file: str = None
) -> Dict[str, Any]:
    """
    Analyze citations to identify top competitors and generate comprehensive report.
    
    Args:
        results: Results from check_visibility_with_citations
        output_file: Optional path to save report (HTML/Markdown)
    
    Returns:
        Dictionary with competitor analysis and report data
    """
    from collections import Counter
    from urllib.parse import urlparse
    
    # Extract all citations
    all_citations = []
    for citation_data in results.get("detailed_citations", []):
        for provider, citations in citation_data.get("citations", {}).items():
            for citation_url in citations:
                all_citations.append({
                    "url": citation_url,
                    "provider": provider,
                    "query": citation_data.get("query", "")
                })
    
    # Extract domains and identify competitors
    domain_counter = Counter()
    url_to_domain = {}
    domain_details = {}
    
    for citation in all_citations:
        url = citation["url"]
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "").lower()
            if domain:
                domain_counter[domain] += 1
                url_to_domain[url] = domain
                
                # Store details for each domain
                if domain not in domain_details:
                    domain_details[domain] = {
                        "domain": domain,
                        "urls": [],
                        "queries_mentioned_in": set(),
                        "providers": set(),
                        "mention_count": 0
                    }
                
                domain_details[domain]["urls"].append(url)
                domain_details[domain]["queries_mentioned_in"].add(citation["query"])
                domain_details[domain]["providers"].add(citation["provider"])
                domain_details[domain]["mention_count"] += 1
        except Exception:
            continue
    
    # Filter out common non-competitor domains
    exclude_domains = {
        "google.com", "facebook.com", "twitter.com", "instagram.com",
        "linkedin.com", "youtube.com", "pinterest.com", "reddit.com",
        "wikipedia.org", "yelp.com", "tripadvisor.com", "map.google.com"
    }
    
    # Rank competitors by citation frequency
    competitor_domains = [
        (domain, count) for domain, count in domain_counter.items()
        if domain not in exclude_domains and count > 0
    ]
    competitor_domains.sort(key=lambda x: x[1], reverse=True)
    
    # Build competitor report
    competitors = []
    business_domain = results.get("business_profile", {}).get("domain", "").replace("www.", "").lower()
    
    for domain, count in competitor_domains[:20]:  # Top 20 competitors
        if domain == business_domain:
            continue  # Skip own domain
        
        details = domain_details.get(domain, {})
        competitors.append({
            "rank": len(competitors) + 1,
            "domain": domain,
            "mention_count": count,
            "queries_appeared_in": len(details.get("queries_mentioned_in", [])),
            "providers_found_in": list(details.get("providers", [])),
            "sample_urls": details.get("urls", [])[:3],  # Top 3 URLs
            "visibility_score": min(1.0, count / len(results.get("detailed_citations", [])) if results.get("detailed_citations") else 1.0)
        })
    
    # Calculate visibility metrics
    total_citations = len(all_citations)
    unique_domains = len(domain_counter)
    
    report_data = {
        "business_profile": results.get("business_profile", {}),
        "citation_summary": {
            "total_citations": total_citations,
            "unique_domains": unique_domains,
            "queries_tested": len(results.get("detailed_citations", [])),
            "providers_checked": results.get("citation_analysis", {}).get("providers_checked", [])
        },
        "top_competitors": competitors,
        "all_citations_by_query": [
            {
                "query": cit_data.get("query", ""),
                "total_citations": len(cit_data.get("citation_sources", [])),
                "citations": cit_data.get("citation_sources", []),
                "business_found": any(cit_data.get("business_found", {}).values())
            }
            for cit_data in results.get("detailed_citations", [])
        ],
        "timestamp": datetime.utcnow().isoformat()
    }
    
    # Generate report text
    if output_file:
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        if output_file.endswith('.html'):
            generate_html_report(report_data, output_file)
        elif output_file.endswith('.md'):
            generate_markdown_report(report_data, output_file)
        else:
            generate_text_report(report_data, output_file)
    
    return report_data


def generate_html_report(data: Dict[str, Any], output_file: str):
    """Generate HTML report."""
    business = data["business_profile"]
    competitors = data["top_competitors"]
    citation_summary = data["citation_summary"]
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Visibility & Competitor Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        .summary-box {{ background: #ecf0f1; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .competitor-table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        .competitor-table th {{ background: #3498db; color: white; padding: 12px; text-align: left; }}
        .competitor-table td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        .competitor-table tr:hover {{ background: #f8f9fa; }}
        .badge {{ display: inline-block; padding: 5px 10px; border-radius: 15px; font-size: 12px; font-weight: bold; }}
        .badge-high {{ background: #e74c3c; color: white; }}
        .badge-medium {{ background: #f39c12; color: white; }}
        .badge-low {{ background: #27ae60; color: white; }}
        .citation-list {{ background: #f8f9fa; padding: 15px; border-radius: 5px; margin: 10px 0; }}
        .citation-item {{ margin: 5px 0; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Visibility & Competitor Analysis Report</h1>
        
        <div class="summary-box">
            <h2>Business Profile</h2>
            <p><strong>Name:</strong> {business.get('name', 'N/A')}</p>
            <p><strong>Domain:</strong> {business.get('domain', 'N/A')}</p>
            <p><strong>Location:</strong> {business.get('city', 'N/A')}, {business.get('state', 'N/A')}</p>
            <p><strong>GMB Rating:</strong> {business.get('gmb_rating', 'N/A')}</p>
        </div>
        
        <div class="summary-box">
            <h2>Citation Summary</h2>
            <p><strong>Total Citations Found:</strong> {citation_summary.get('total_citations', 0)}</p>
            <p><strong>Unique Domains:</strong> {citation_summary.get('unique_domains', 0)}</p>
            <p><strong>Queries Tested:</strong> {citation_summary.get('queries_tested', 0)}</p>
            <p><strong>AI Providers Checked:</strong> {', '.join(citation_summary.get('providers_checked', []))}</p>
        </div>
        
        <h2>Top Visible Competitors</h2>
        <table class="competitor-table">
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Domain</th>
                    <th>Mention Count</th>
                    <th>Queries Appeared In</th>
                    <th>Visibility Score</th>
                    <th>Sample URLs</th>
                </tr>
            </thead>
            <tbody>
"""
    
    for comp in competitors:
        visibility_class = "badge-high" if comp["visibility_score"] > 0.5 else "badge-medium" if comp["visibility_score"] > 0.2 else "badge-low"
        sample_urls = "<br>".join([f'<a href="{url}" target="_blank">{url[:50]}...</a>' for url in comp.get("sample_urls", [])])
        
        html += f"""
                <tr>
                    <td><strong>#{comp['rank']}</strong></td>
                    <td><strong>{comp['domain']}</strong></td>
                    <td>{comp['mention_count']}</td>
                    <td>{comp['queries_appeared_in']}</td>
                    <td><span class="badge {visibility_class}">{comp['visibility_score']:.2%}</span></td>
                    <td>{sample_urls or 'N/A'}</td>
                </tr>
"""
    
    html += """
            </tbody>
        </table>
        
        <h2>Citations by Query</h2>
"""
    
    for query_data in data.get("all_citations_by_query", []):
        found_badge = '<span class="badge badge-high">FOUND</span>' if query_data["business_found"] else '<span class="badge badge-low">NOT FOUND</span>'
        html += f"""
        <div class="citation-list">
            <h3>{query_data['query']} {found_badge}</h3>
            <p><strong>Total Citations:</strong> {query_data['total_citations']}</p>
            <ul>
"""
        for citation in query_data.get("citations", [])[:10]:  # Top 10 per query
            html += f'                <li class="citation-item"><a href="{citation}" target="_blank">{citation}</a></li>\n'
        html += """
            </ul>
        </div>
"""
    
    html += """
        <p style="margin-top: 40px; color: #7f8c8d; font-size: 12px;">
            Report generated: """ + data.get("timestamp", "") + """
        </p>
    </div>
</body>
</html>
"""
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_markdown_report(data: Dict[str, Any], output_file: str):
    """Generate Markdown report."""
    business = data["business_profile"]
    competitors = data["top_competitors"]
    citation_summary = data["citation_summary"]
    
    md = f"""# Visibility & Competitor Analysis Report

## Business Profile

- **Name:** {business.get('name', 'N/A')}
- **Domain:** {business.get('domain', 'N/A')}
- **Location:** {business.get('city', 'N/A')}, {business.get('state', 'N/A')}
- **GMB Rating:** {business.get('gmb_rating', 'N/A')}

## Citation Summary

- **Total Citations Found:** {citation_summary.get('total_citations', 0)}
- **Unique Domains:** {citation_summary.get('unique_domains', 0)}
- **Queries Tested:** {citation_summary.get('queries_tested', 0)}
- **AI Providers Checked:** {', '.join(citation_summary.get('providers_checked', []))}

## Top Visible Competitors

| Rank | Domain | Mention Count | Queries Appeared In | Visibility Score |
|------|--------|---------------|---------------------|------------------|
"""
    
    for comp in competitors:
        md += f"| #{comp['rank']} | **{comp['domain']}** | {comp['mention_count']} | {comp['queries_appeared_in']} | {comp['visibility_score']:.2%} |\n"
    
    md += "\n## Citations by Query\n\n"
    
    for query_data in data.get("all_citations_by_query", []):
        found_status = "✓ FOUND" if query_data["business_found"] else "✗ NOT FOUND"
        md += f"### {query_data['query']} - {found_status}\n\n"
        md += f"**Total Citations:** {query_data['total_citations']}\n\n"
        md += "**Citations:**\n"
        for citation in query_data.get("citations", []):
            md += f"- {citation}\n"
        md += "\n"
    
    md += f"\n---\n*Report generated: {data.get('timestamp', '')}*\n"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md)


def generate_text_report(data: Dict[str, Any], output_file: str):
    """Generate plain text report."""
    business = data["business_profile"]
    competitors = data["top_competitors"]
    citation_summary = data["citation_summary"]
    
    text = f"""
================================================================================
VISIBILITY & COMPETITOR ANALYSIS REPORT
================================================================================

BUSINESS PROFILE
--------------------------------------------------------------------------------
Name: {business.get('name', 'N/A')}
Domain: {business.get('domain', 'N/A')}
Location: {business.get('city', 'N/A')}, {business.get('state', 'N/A')}
GMB Rating: {business.get('gmb_rating', 'N/A')}

CITATION SUMMARY
--------------------------------------------------------------------------------
Total Citations Found: {citation_summary.get('total_citations', 0)}
Unique Domains: {citation_summary.get('unique_domains', 0)}
Queries Tested: {citation_summary.get('queries_tested', 0)}
AI Providers Checked: {', '.join(citation_summary.get('providers_checked', []))}

TOP VISIBLE COMPETITORS
--------------------------------------------------------------------------------
"""
    
    for comp in competitors:
        text += f"\n#{comp['rank']}: {comp['domain']}\n"
        text += f"  Mention Count: {comp['mention_count']}\n"
        text += f"  Queries Appeared In: {comp['queries_appeared_in']}\n"
        text += f"  Visibility Score: {comp['visibility_score']:.2%}\n"
        text += f"  Sample URLs:\n"
        for url in comp.get("sample_urls", [])[:3]:
            text += f"    - {url}\n"
    
    text += "\n\nCITATIONS BY QUERY\n"
    text += "=" * 80 + "\n\n"
    
    for query_data in data.get("all_citations_by_query", []):
        found_status = "[FOUND]" if query_data["business_found"] else "[NOT FOUND]"
        text += f"Query: {query_data['query']} {found_status}\n"
        text += f"Total Citations: {query_data['total_citations']}\n"
        text += "Citations:\n"
        for citation in query_data.get("citations", []):
            text += f"  - {citation}\n"
        text += "\n"
    
    text += f"\nReport generated: {data.get('timestamp', '')}\n"
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(text)


async def process_batch_with_citations(
    urls: List[str],
    location_target: str = "city",
    max_queries: int = 10,
    providers: List[str] = ["openai", "perplexity"],
    output_file: str = None
) -> List[Dict[str, Any]]:
    """Process multiple URLs with citation tracking."""
    print("="*80)
    print(f"BATCH PROCESSING: {len(urls)} websites")
    print(f"Location Target: {location_target}")
    print(f"Max Queries per Site: {max_queries}")
    print(f"Citation Providers: {', '.join(providers)}")
    print("="*80)
    
    results = []
    for idx, url in enumerate(urls, 1):
        print(f"\n{'='*80}")
        print(f"[{idx}/{len(urls)}] Processing: {url}")
        print(f"{'='*80}")
        
        try:
            result = await check_visibility_with_citations(
                url,
                location_target=location_target,
                max_queries=max_queries,
                providers=providers,
                firecrawl_key=None,  # Could add to process_batch_with_citations signature
                qdrant_url=None,
                qdrant_key=None
            )
            results.append(result)
        except Exception as e:
            print(f"ERROR: {str(e)}")
            results.append({
                "url": url,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            })
    
    # Save results
    if output_file:
        os.makedirs(os.path.dirname(output_file) if os.path.dirname(output_file) else ".", exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nResults saved to: {output_file}")
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check visibility with automated prompt engineering and citation tracking'
    )
    parser.add_argument('urls', nargs='*', help='URLs to check')
    parser.add_argument('--file', '-f', help='Text file with URLs (one per line)')
    parser.add_argument('--location-target', '-l', default='city',
                       choices=['city', 'state', 'nationwide', 'general'],
                       help='Location targeting mode')
    parser.add_argument('--max-queries', '-q', type=int, default=10,
                       help='Maximum queries per website')
    parser.add_argument('--goal', '-g', default='visibility_check',
                       choices=['visibility_check', 'lead_generation', 'market_analysis', 'competitor_research'],
                       help='Goal for prompt generation (default: visibility_check)')
    parser.add_argument('--providers', '-p', nargs='+',
                       default=['openai', 'perplexity'],
                       choices=['openai', 'perplexity', 'gemini'],
                       help='AI providers to check citations from')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--firecrawl-key', help='Firecrawl API key (overrides env var)')
    parser.add_argument('--qdrant-url', help='Qdrant URL (overrides env var, default: http://localhost:6333)')
    parser.add_argument('--qdrant-key', help='Qdrant API key (overrides env var)')
    
    args = parser.parse_args()
    
    # Set API keys from arguments if provided
    if args.firecrawl_key:
        os.environ['FIRECRAWL_API_KEY'] = args.firecrawl_key
    if args.qdrant_url:
        os.environ['QDRANT_URL'] = args.qdrant_url
    if args.qdrant_key:
        os.environ['QDRANT_API_KEY'] = args.qdrant_key
    
    # Load URLs
    urls = []
    if args.file and os.path.exists(args.file):
        with open(args.file, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'):
                    if not url.startswith(('http://', 'https://')):
                        url = f"https://{url}"
                    urls.append(url)
    
    if args.urls:
        urls.extend([u if u.startswith(('http://', 'https://')) else f"https://{u}" 
                    for u in args.urls])
    
    if not urls:
        print("Error: No URLs provided")
        print("\nUsage examples:")
        print("  python test_visibility_with_citations.py https://example.com")
        print("  python test_visibility_with_citations.py --file urls.txt --providers openai perplexity gemini")
        print("  python test_visibility_with_citations.py https://site1.com https://site2.com --location-target state")
        sys.exit(1)
    
    # Run
    output_file = args.output or f"results/visibility_citations_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    if len(urls) == 1:
        result = asyncio.run(check_visibility_with_citations(
            urls[0],
            location_target=args.location_target,
            max_queries=args.max_queries,
            providers=args.providers,
            firecrawl_key=args.firecrawl_key,
            qdrant_url=args.qdrant_url,
            qdrant_key=args.qdrant_key,
            goal=args.goal
        ))
        
        # Generate competitor analysis and report
        print("\n" + "="*80)
        print("GENERATING COMPETITOR ANALYSIS REPORT")
        print("="*80)
        
        report_data = analyze_competitors_and_generate_report(result)
        
        # Save JSON results
        json_file = args.output if args.output and args.output.endswith('.json') else output_file
        os.makedirs(os.path.dirname(json_file) if os.path.dirname(json_file) else ".", exist_ok=True)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nJSON results saved to: {json_file}")
        
        # Generate reports
        base_name = json_file.replace('.json', '')
        report_data_html = analyze_competitors_and_generate_report(result, f"{base_name}_report.html")
        report_data_md = analyze_competitors_and_generate_report(result, f"{base_name}_report.md")
        report_data_txt = analyze_competitors_and_generate_report(result, f"{base_name}_report.txt")
        
        print(f"HTML report saved to: {base_name}_report.html")
        print(f"Markdown report saved to: {base_name}_report.md")
        print(f"Text report saved to: {base_name}_report.txt")
        
        # Print summary
        if report_data.get("top_competitors"):
            print("\n" + "="*80)
            print("TOP 5 COMPETITORS")
            print("="*80)
            for comp in report_data["top_competitors"][:5]:
                print(f"#{comp['rank']}: {comp['domain']} - {comp['mention_count']} mentions "
                      f"({comp['visibility_score']:.1%} visibility)")
    else:
        asyncio.run(process_batch_with_citations(
            urls,
            location_target=args.location_target,
            max_queries=args.max_queries,
            providers=args.providers,
            output_file=output_file
        ))

