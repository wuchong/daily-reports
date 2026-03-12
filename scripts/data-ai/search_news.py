#!/usr/bin/env python3
"""Search and collect news from Google API and RSS feeds."""

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import feedparser
import requests
import yaml


def load_sources():
    """Load sources configuration."""
    config_path = Path(__file__).parent / 'sources.yaml'
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def search_serper(query: str, api_key: str) -> list:
    """Search using Serper.dev API (free tier: 2500/month)."""
    url = "https://google.serper.dev/search"
    headers = {
        'X-API-KEY': api_key,
        'Content-Type': 'application/json'
    }
    payload = {
        'q': query,
        'num': 10,
        'tbs': 'qdr:d'  # Last 24 hours
    }
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        results = []
        for item in data.get('organic', []):
            results.append({
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'snippet': item.get('snippet', ''),
                'source': 'serper_search',
                'query': query
            })
        return results
    except Exception as e:
        print(f"Serper search error for '{query}': {e}")
        return []


def fetch_rss(feed_config: dict) -> list:
    """Fetch and parse RSS feed."""
    try:
        feed = feedparser.parse(feed_config['url'])
        results = []
        cutoff = datetime.now() - timedelta(days=1)
        
        for entry in feed.entries[:10]:
            # Parse published date
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6])
            
            # Filter by date
            if published and published < cutoff:
                continue
            
            results.append({
                'title': entry.get('title', ''),
                'url': entry.get('link', ''),
                'snippet': entry.get('summary', '')[:500] if entry.get('summary') else '',
                'source': feed_config['name'],
                'published': published.isoformat() if published else None
            })
        return results
    except Exception as e:
        print(f"RSS fetch error for '{feed_config['name']}': {e}")
        return []


def deduplicate(items: list) -> list:
    """Remove duplicate URLs."""
    seen = set()
    unique = []
    for item in items:
        url = item.get('url', '')
        if url and url not in seen:
            seen.add(url)
            unique.append(item)
    return unique


def main():
    """Main entry point."""
    # Load config
    sources = load_sources()
    api_key = os.environ.get('SERPER_API_KEY')
    report_date = os.environ.get('REPORT_DATE', datetime.now().strftime('%Y-%m-%d'))
    
    all_results = []
    
    # Search using Serper.dev API
    if api_key:
        queries = []
        for tier in ['tier_1', 'tier_2', 'tier_3', 'conditional']:
            queries.extend(sources['search']['queries'].get(tier, []))
        
        print(f"Searching {len(queries)} queries via Serper.dev...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(search_serper, q, api_key): q for q in queries}
            for future in as_completed(futures):
                results = future.result()
                all_results.extend(results)
    else:
        print("Warning: SERPER_API_KEY not set, skipping search")
    
    # Fetch RSS feeds
    print(f"Fetching {len(sources.get('blogs', []))} RSS feeds...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss, blog): blog['name'] for blog in sources.get('blogs', [])}
        for future in as_completed(futures):
            results = future.result()
            all_results.extend(results)
    
    # Deduplicate
    unique_results = deduplicate(all_results)
    print(f"Collected {len(unique_results)} unique items")
    
    # Save output
    output = {
        'date': report_date,
        'collected_at': datetime.now().isoformat(),
        'items': unique_results
    }
    
    with open('raw_news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("Saved to raw_news.json")


if __name__ == '__main__':
    main()
