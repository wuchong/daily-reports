#!/usr/bin/env python3
"""Fetch emails from Apache mailing list via Pony Mail API.

Environment variables:
- LIST_NAME: Mailing list name (default: dev)
- LIST_DOMAIN: Mailing list domain (e.g., flink.apache.org)
- REPORT_WEEK: Report week in YYYY-Www format (optional)
"""

import asyncio
import json
import os
from datetime import date, datetime, timedelta

import aiohttp


PONYMAIL_BASE = "https://lists.apache.org/api"
CONCURRENT_LIMIT = 30


async def fetch_stats(session: aiohttp.ClientSession, list_name: str, domain: str) -> dict:
    """Fetch email list and thread structure from stats.lua API."""
    url = f"{PONYMAIL_BASE}/stats.lua"
    params = {
        "list": list_name,
        "domain": domain,
        "d": "lte=7d"
    }
    async with session.get(url, params=params) as resp:
        resp.raise_for_status()
        return await resp.json()


async def fetch_email_content(
    session: aiohttp.ClientSession,
    mid: str,
    semaphore: asyncio.Semaphore
) -> dict:
    """Fetch single email content from email.lua API."""
    async with semaphore:
        url = f"{PONYMAIL_BASE}/email.lua"
        params = {"id": mid}
        try:
            async with session.get(url, params=params, timeout=30) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    print(f"Failed to fetch {mid}: HTTP {resp.status}")
                    return None
        except Exception as e:
            print(f"Error fetching {mid}: {e}")
            return None


async def fetch_all_emails(
    session: aiohttp.ClientSession,
    email_mids: list[str]
) -> list[dict]:
    """Fetch all email contents concurrently."""
    semaphore = asyncio.Semaphore(CONCURRENT_LIMIT)
    tasks = [
        fetch_email_content(session, mid, semaphore)
        for mid in email_mids
    ]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]


def calculate_week_range(week_str: str | None) -> tuple[str, str, str]:
    """Calculate week string and date range.
    
    Args:
        week_str: Optional week in YYYY-Www format
        
    Returns:
        (week, start_date, end_date) tuple
    """
    if week_str:
        # Parse YYYY-Www format
        year, week_num = week_str.split("-W")
        year = int(year)
        week_num = int(week_num)
    else:
        # Default to last week
        today = datetime.now()
        last_monday = today - timedelta(days=today.weekday() + 7)
        year, week_num, _ = last_monday.isocalendar()
    
    # Calculate start (Monday) and end (Sunday) of the week
    start = date.fromisocalendar(year, week_num, 1)
    end = date.fromisocalendar(year, week_num, 7)
    
    return f"{year}-W{week_num:02d}", start.isoformat(), end.isoformat()


async def main():
    """Main entry point."""
    # Get configuration from environment
    list_name = os.environ.get("LIST_NAME", "dev")
    list_domain = os.environ.get("LIST_DOMAIN", "")
    
    if not list_domain:
        print("Error: LIST_DOMAIN environment variable is required")
        return
    
    week_input = os.environ.get("REPORT_WEEK", "")
    week, start_date, end_date = calculate_week_range(week_input if week_input else None)
    
    print(f"Fetching emails from {list_name}@{list_domain}")
    print(f"Week: {week} ({start_date} ~ {end_date})")
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Get email list and thread structure
        print("Fetching email list from stats.lua...")
        stats = await fetch_stats(session, list_name, list_domain)
        
        emails_meta = stats.get("emails", [])
        thread_struct = stats.get("thread_struct", [])
        
        print(f"Found {len(emails_meta)} emails")
        
        # Step 2: Fetch full content for each email
        email_mids = [e.get("mid") or e.get("id") for e in emails_meta if e.get("mid") or e.get("id")]
        print(f"Fetching {len(email_mids)} email contents concurrently...")
        
        emails_full = await fetch_all_emails(session, email_mids)
        print(f"Successfully fetched {len(emails_full)} emails")
    
    # Build output
    output = {
        "week": week,
        "date_range": {
            "start": start_date,
            "end": end_date
        },
        "emails": emails_full,
        "thread_struct": thread_struct
    }
    
    # Save to file
    with open("raw_emails.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"Saved {len(emails_full)} emails to raw_emails.json")


if __name__ == "__main__":
    asyncio.run(main())
