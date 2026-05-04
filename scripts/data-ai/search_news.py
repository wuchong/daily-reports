#!/usr/bin/env python3
"""Search and collect news from Google API and RSS feeds."""

import json
import os
import re
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


def parse_serper_date(date_str: str) -> datetime | None:
    """Parse Serper date string to datetime.
    
    Supports formats:
    - Relative: '2 hours ago', '23 hours ago', '1 day ago', '3 days ago'
    - Absolute: 'Jan 27, 2026', 'Feb 3, 2026'
    """
    if not date_str:
        return None
    
    now = datetime.now()
    
    # Try relative time format
    relative_match = re.match(r'(\d+)\s+(hour|day|minute|week|month)s?\s+ago', date_str, re.I)
    if relative_match:
        amount = int(relative_match.group(1))
        unit = relative_match.group(2).lower()
        if unit == 'minute':
            return now - timedelta(minutes=amount)
        elif unit == 'hour':
            return now - timedelta(hours=amount)
        elif unit == 'day':
            return now - timedelta(days=amount)
        elif unit == 'week':
            return now - timedelta(weeks=amount)
        elif unit == 'month':
            return now - timedelta(days=amount * 30)
    
    # Try absolute date format (e.g., 'Jan 27, 2026')
    try:
        return datetime.strptime(date_str, '%b %d, %Y')
    except ValueError:
        pass
    
    # Try other common formats
    for fmt in ['%B %d, %Y', '%Y-%m-%d', '%d %b %Y']:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def fetch_article(url: str, timeout: int = 10) -> dict:
    """Fetch article content and parse publish date from URL."""
    import re
    from bs4 import BeautifulSoup
    
    result = {'content': '', 'published': None, 'error': None}
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. Try JSON-LD for datePublished
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                import json
                ld_data = json.loads(script.string)
                if isinstance(ld_data, list):
                    ld_data = ld_data[0] if ld_data else {}
                date_str = ld_data.get('datePublished') or ld_data.get('dateCreated')
                if date_str:
                    result['published'] = parse_iso_date(date_str)
                    break
            except:
                continue
        
        # 2. Try meta tags
        if not result['published']:
            date_metas = [
                ('property', 'article:published_time'),
                ('name', 'pubdate'),
                ('name', 'date'),
                ('name', 'DC.date.issued'),
                ('itemprop', 'datePublished'),
            ]
            for attr, value in date_metas:
                meta = soup.find('meta', {attr: value})
                if meta and meta.get('content'):
                    result['published'] = parse_iso_date(meta['content'])
                    if result['published']:
                        break
        
        # 3. Extract main content
        # Remove script, style, nav, header, footer
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'form']):
            tag.decompose()
        
        # Try article tag first, then main, then body
        main_content = soup.find('article') or soup.find('main') or soup.find('body')
        if main_content:
            # Get text, clean up whitespace
            text = main_content.get_text(separator='\n', strip=True)
            # Limit content length
            result['content'] = text[:5000] if len(text) > 5000 else text
        
    except Exception as e:
        result['error'] = str(e)
    
    return result


def parse_iso_date(date_str: str) -> datetime | None:
    """Parse ISO format date string. Always returns offset-naive datetime."""
    if not date_str:
        return None
    
    # Remove timezone info for simpler parsing (always return naive datetime)
    clean_date = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)
    clean_date = clean_date.replace('Z', '')
    # Also handle +0800 format (without colon)
    clean_date = re.sub(r'[+-]\d{4}$', '', clean_date)
    
    formats = [
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d',
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(clean_date, fmt)
        except ValueError:
            continue
    
    return None


def search_serper(query: str, api_key: str, max_age_hours: int = 24) -> list:
    """Search using Serper.dev API and fetch article content."""
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
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        
        for item in data.get('organic', []):
            # Parse and filter by date
            date_str = item.get('date', '')
            published = parse_serper_date(date_str)
            
            # Skip if date is available and older than cutoff
            if published and published < cutoff:
                continue
            
            results.append({
                'title': item.get('title', ''),
                'url': item.get('link', ''),
                'snippet': item.get('snippet', ''),
                'source': 'serper_search',
                'query': query,
                'date': date_str,
                'published': published.isoformat() if published else None
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
    
    # Fetch RSS feeds first (higher priority - blog content is richer)
    blogs = sources.get('blogs', [])
    print(f"Fetching {len(blogs)} RSS feeds...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_rss, blog): blog.get('name', 'unknown') for blog in blogs}
        for future in as_completed(futures):
            try:
                results = future.result()
                all_results.extend(results)
            except Exception as e:
                print(f"Error in RSS future: {e}")
    
    # Search using Serper.dev API (lower priority - may duplicate blog entries)
    if api_key:
        queries = []
        for tier in ['tier_1', 'tier_2', 'tier_3', 'conditional']:
            queries.extend(sources['search']['queries'].get(tier, []))
        
        print(f"Searching {len(queries)} queries via Serper.dev...")
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(search_serper, q, api_key): q for q in queries}
            for future in as_completed(futures):
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error in search future: {e}")
    else:
        print("Warning: SERPER_API_KEY not set, skipping search")
    
    # Deduplicate
    unique_results = deduplicate(all_results)
    print(f"Collected {len(unique_results)} unique items")
    
    # Fetch article content and verify publish dates
    print(f"Fetching article content for {len(unique_results)} items...")
    cutoff = datetime.now() - timedelta(hours=24)
    verified_results = []
    
    def process_article(item):
        """Fetch article and verify date."""
        try:
            url = item.get('url', '')
            if not url:
                return None
            
            article = fetch_article(url)
            
            # Use fetched publish date if available, otherwise keep original
            if article['published']:
                item['published'] = article['published'].isoformat()
                item['published_verified'] = True
            else:
                item['published_verified'] = False
            
            # Add content for LLM summarization
            if article['content']:
                item['content'] = article['content']
            
            # Filter by verified date
            if article['published'] and article['published'] < cutoff:
                return None  # Skip old news
            
            return item
        except Exception as e:
            print(f"Error processing article {item.get('url', 'unknown')}: {e}")
            return None
    
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_article, item): item.get('url', 'unknown') for item in unique_results}
        for future in as_completed(futures):
            try:
                result = future.result()
                if result:
                    verified_results.append(result)
            except Exception as e:
                print(f"Error in future result: {e}")
    
    print(f"Verified {len(verified_results)} items within 24 hours")
    
    # Save output
    output = {
        'date': report_date,
        'collected_at': datetime.now().isoformat(),
        'items': verified_results
    }
    
    with open('raw_news.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print("Saved to raw_news.json")


if __name__ == '__main__':
    main()
