# Flink Dev Weekly Report Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated weekly report system that fetches Flink dev mailing list emails, categorizes them (Announce/Vote/Discussion/JIRA), generates summaries via LLM, and publishes to DingTalk + GitHub Pages.

**Architecture:** Two-stage email fetching (stats.lua for list → email.lua for content with concurrent IO), rule-based classification, LLM summarization for discussions/votes/JIRA, HTML report generation, DingTalk markdown push, GitHub Pages deployment.

**Tech Stack:** Python 3.11, asyncio + aiohttp (concurrent fetching), OpenAI-compatible LLM API, GitHub Actions

**Spec:** [2026-03-13-flink-dev-weekly-report-design.md](../specs/2026-03-13-flink-dev-weekly-report-design.md)

---

## File Structure

```
scripts/flink-dev/
├── fetch_emails.py      # Two-stage email fetching with concurrent IO
├── generate_summary.py  # LLM summarization for discussions/votes/JIRA
├── generate_report.py   # HTML report generation
└── send_dingtalk.py     # DingTalk markdown push

prompts/
└── flink-dev-summarize.md   # LLM prompt templates

assets/flink-dev/
└── style.css            # Report styles

.github/workflows/
└── flink-dev-weekly-report.yml  # GitHub Actions workflow
```

---

## Chunk 1: Email Fetching

### Task 1: Create fetch_emails.py with stats.lua API

**Files:**
- Create: `scripts/flink-dev/fetch_emails.py`

- [ ] **Step 1: Create fetch_emails.py with basic structure**

```python
#!/usr/bin/env python3
"""Fetch emails from Apache Flink dev mailing list via Pony Mail API."""

import asyncio
import json
import os
from datetime import datetime, timedelta

import aiohttp


PONYMAIL_BASE = "https://lists.apache.org/api"
LIST_NAME = "dev"
DOMAIN = "flink.apache.org"
CONCURRENT_LIMIT = 30


async def fetch_stats(session: aiohttp.ClientSession) -> dict:
    """Fetch email list and thread structure from stats.lua API."""
    url = f"{PONYMAIL_BASE}/stats.lua"
    params = {
        "list": LIST_NAME,
        "domain": DOMAIN,
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
    from datetime import date
    start = date.fromisocalendar(year, week_num, 1)
    end = date.fromisocalendar(year, week_num, 7)
    
    return f"{year}-W{week_num:02d}", start.isoformat(), end.isoformat()


async def main():
    """Main entry point."""
    week_input = os.environ.get("REPORT_WEEK", "")
    week, start_date, end_date = calculate_week_range(week_input if week_input else None)
    
    print(f"Fetching emails for {week} ({start_date} ~ {end_date})")
    
    async with aiohttp.ClientSession() as session:
        # Step 1: Get email list and thread structure
        print("Fetching email list from stats.lua...")
        stats = await fetch_stats(session)
        
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
```

- [ ] **Step 2: Test locally (dry run)**

```bash
cd /Users/wuchong/Workspace/Fluss/daily-reports
pip install aiohttp
python scripts/flink-dev/fetch_emails.py
# Expected: Creates raw_emails.json with fetched emails
```

- [ ] **Step 3: Commit**

```bash
git add scripts/flink-dev/fetch_emails.py
git commit -m "feat(flink-dev): add email fetching with concurrent IO"
```

---

## Chunk 2: Email Classification

### Task 2: Add classification logic to process fetched emails

**Files:**
- Create: `scripts/flink-dev/classify_emails.py`

- [ ] **Step 1: Create classify_emails.py**

```python
#!/usr/bin/env python3
"""Classify emails into categories: Announce, Vote, Discussion, JIRA."""

import json
import re
from collections import defaultdict


# Classification patterns (priority order: JIRA > Announce > Vote > Discussion)
PATTERNS = {
    "jira": re.compile(r"\[jira\]", re.IGNORECASE),
    "announce": re.compile(r"\[ANNOUNCE\]", re.IGNORECASE),
    "vote": re.compile(r"\[(VOTE|RESULT)\]", re.IGNORECASE),
    "discuss": re.compile(r"\[DISCUSS\]", re.IGNORECASE),
}

# Objection patterns for votes
OBJECTION_PATTERNS = re.compile(r"(?:^|\s)([+-]0|-1)(?:\s|$|,|\.)")


def clean_subject(subject: str) -> str:
    """Remove classification tags from subject."""
    cleaned = subject
    for pattern in PATTERNS.values():
        cleaned = pattern.sub("", cleaned)
    # Also remove Re: prefix for display
    cleaned = re.sub(r"^(Re:\s*)+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def get_thread_root(subject: str) -> str:
    """Extract thread root subject (remove Re: prefix)."""
    return re.sub(r"^(Re:\s*)+", "", subject, flags=re.IGNORECASE).strip()


def classify_email(subject: str) -> str:
    """Classify email by subject. Returns category name."""
    # Priority order
    if PATTERNS["jira"].search(subject):
        return "jira"
    if PATTERNS["announce"].search(subject):
        return "announce"
    if PATTERNS["vote"].search(subject):
        return "vote"
    # Everything else is discussion (including [DISCUSS] tagged)
    return "discussion"


def has_objection(body: str) -> bool:
    """Check if email body contains voting objection (-1, +0, -0)."""
    if not body:
        return False
    # Check first few lines where votes typically appear
    lines = body.split("\n")[:20]
    text = "\n".join(lines)
    return bool(OBJECTION_PATTERNS.search(text))


def build_thread_link(mid: str) -> str:
    """Build permalink for email thread."""
    return f"https://lists.apache.org/thread/{mid}"


def group_into_threads(emails: list[dict]) -> dict[str, list[dict]]:
    """Group emails by thread root subject."""
    threads = defaultdict(list)
    for email in emails:
        subject = email.get("subject", "")
        root = get_thread_root(subject)
        threads[root].append(email)
    return dict(threads)


def process_emails(raw_data: dict) -> dict:
    """Process raw emails into categorized threads."""
    emails = raw_data.get("emails", [])
    
    # Classify all emails
    categorized = {
        "announce": [],
        "vote": [],
        "discussion": [],
        "jira": []
    }
    
    for email in emails:
        subject = email.get("subject", "")
        category = classify_email(subject)
        categorized[category].append(email)
    
    # Process each category
    result = {
        "week": raw_data.get("week"),
        "date_range": raw_data.get("date_range"),
        "announcements": [],
        "votes": [],
        "discussions": [],
        "jira_count": len(categorized["jira"]),
        "jira_titles": [e.get("subject", "") for e in categorized["jira"]]
    }
    
    # Announcements: group by thread, take root email
    announce_threads = group_into_threads(categorized["announce"])
    for root_subject, thread_emails in announce_threads.items():
        # Sort by epoch to get first email
        thread_emails.sort(key=lambda e: e.get("epoch", 0))
        root_email = thread_emails[0]
        result["announcements"].append({
            "subject": clean_subject(root_subject),
            "link": build_thread_link(root_email.get("mid", "")),
            "from": root_email.get("from", ""),
            "date": root_email.get("date", "")
        })
    
    # Votes: group by thread, check for objections
    vote_threads = group_into_threads(categorized["vote"])
    for root_subject, thread_emails in vote_threads.items():
        thread_emails.sort(key=lambda e: e.get("epoch", 0))
        root_email = thread_emails[0]
        
        # Check for objections in replies
        objection_emails = []
        for email in thread_emails[1:]:  # Skip root
            body = email.get("body", "")
            if has_objection(body):
                objection_emails.append({
                    "from": email.get("from", ""),
                    "body": body,
                    "mid": email.get("mid", "")
                })
        
        result["votes"].append({
            "subject": clean_subject(root_subject),
            "link": build_thread_link(root_email.get("mid", "")),
            "from": root_email.get("from", ""),
            "date": root_email.get("date", ""),
            "reply_count": len(thread_emails) - 1,
            "has_objection": len(objection_emails) > 0,
            "objection_emails": objection_emails
        })
    
    # Discussions: group by thread
    discussion_threads = group_into_threads(categorized["discussion"])
    for root_subject, thread_emails in discussion_threads.items():
        thread_emails.sort(key=lambda e: e.get("epoch", 0))
        root_email = thread_emails[0]
        
        # Collect participants
        participants = list(set(e.get("from", "") for e in thread_emails))
        
        result["discussions"].append({
            "subject": clean_subject(root_subject),
            "link": build_thread_link(root_email.get("mid", "")),
            "from": root_email.get("from", ""),
            "date": root_email.get("date", ""),
            "reply_count": len(thread_emails) - 1,
            "participants": participants,
            "emails": thread_emails  # Full emails for LLM summarization
        })
    
    # Sort discussions by reply count (most active first)
    result["discussions"].sort(key=lambda d: d["reply_count"], reverse=True)
    
    return result


def main():
    """Main entry point."""
    # Load raw emails
    with open("raw_emails.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    
    print(f"Processing {len(raw_data.get('emails', []))} emails...")
    
    # Process and classify
    threads = process_emails(raw_data)
    
    print(f"Categories:")
    print(f"  - Announcements: {len(threads['announcements'])}")
    print(f"  - Votes: {len(threads['votes'])}")
    print(f"  - Discussions: {len(threads['discussions'])}")
    print(f"  - JIRA: {threads['jira_count']}")
    
    # Save to file
    with open("threads.json", "w", encoding="utf-8") as f:
        json.dump(threads, f, ensure_ascii=False, indent=2)
    
    print("Saved to threads.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test locally**

```bash
python scripts/flink-dev/classify_emails.py
# Expected: Creates threads.json with categorized emails
```

- [ ] **Step 3: Commit**

```bash
git add scripts/flink-dev/classify_emails.py
git commit -m "feat(flink-dev): add email classification logic"
```

---

## Chunk 3: LLM Summarization

### Task 3: Create LLM prompt template

**Files:**
- Create: `prompts/flink-dev-summarize.md`

- [ ] **Step 1: Create prompt file**

```markdown
# Flink 社区周报摘要生成

## 讨论摘要任务

你是 Apache Flink 社区的技术分析师。请根据以下邮件讨论内容，生成简洁的中文摘要。

要求：
1. 用 2-3 句话概括讨论的核心议题和进展
2. 列出主要参与者的关键观点（最多 3 个）
3. 如有初步结论或下一步行动，请指出

输出 JSON 格式：
```json
{
  "summary": "本周讨论了...",
  "key_points": [
    {"author": "xxx", "point": "认为应该..."}
  ],
  "conclusion": "社区倾向于..."
}
```

## 投票异议任务

请根据以下投票回复，简述异议原因（1-2 句话）。

输出 JSON 格式：
```json
{
  "objection_summary": "xxx 提出 -1，原因是..."
}
```

## JIRA 摘要任务

请根据以下 JIRA 邮件标题列表，生成 2-3 句话的整体摘要，概括本周 JIRA 主要涉及哪些方面。

输出 JSON 格式：
```json
{
  "jira_summary": "本周 JIRA 主要集中在..."
}
```
```

- [ ] **Step 2: Commit**

```bash
git add prompts/flink-dev-summarize.md
git commit -m "feat(flink-dev): add LLM prompt templates"
```

### Task 4: Create generate_summary.py

**Files:**
- Create: `scripts/flink-dev/generate_summary.py`

- [ ] **Step 1: Create generate_summary.py**

```python
#!/usr/bin/env python3
"""Generate summaries for discussions, votes, and JIRA using LLM."""

import json
import os
from pathlib import Path

from openai import OpenAI


def load_prompt() -> str:
    """Load prompt template."""
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "flink-dev-summarize.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def create_client() -> OpenAI:
    """Create OpenAI client with custom base URL if configured."""
    return OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY")
    )


def extract_author_name(from_field: str) -> str:
    """Extract author name from email 'from' field."""
    # Format: "Name <email>" or just "email"
    if "<" in from_field:
        return from_field.split("<")[0].strip().strip('"')
    return from_field.split("@")[0]


def summarize_discussion(client: OpenAI, discussion: dict) -> dict:
    """Generate summary for a discussion thread."""
    emails = discussion.get("emails", [])
    
    # Build email content for LLM
    email_texts = []
    for email in emails[:15]:  # Limit to first 15 emails
        author = extract_author_name(email.get("from", ""))
        body = email.get("body", "")[:2000]  # Truncate long emails
        email_texts.append(f"From: {author}\n{body}")
    
    content = "\n\n---\n\n".join(email_texts)
    
    prompt = f"""请根据以下邮件讨论内容，生成简洁的中文摘要。

要求：
1. 用 2-3 句话概括讨论的核心议题和进展
2. 列出主要参与者的关键观点（最多 3 个）
3. 如有初步结论或下一步行动，请指出

输出 JSON 格式：
{{"summary": "...", "key_points": [{{"author": "...", "point": "..."}}], "conclusion": "..."}}

讨论主题: {discussion.get('subject', '')}

邮件内容:
{content}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error summarizing discussion '{discussion.get('subject', '')}': {e}")
        return {"summary": "摘要生成失败", "key_points": [], "conclusion": ""}


def summarize_objection(client: OpenAI, vote: dict) -> str:
    """Generate summary for vote objections."""
    objection_emails = vote.get("objection_emails", [])
    if not objection_emails:
        return ""
    
    # Build objection content
    objection_texts = []
    for email in objection_emails[:5]:
        author = extract_author_name(email.get("from", ""))
        body = email.get("body", "")[:1000]
        objection_texts.append(f"From: {author}\n{body}")
    
    content = "\n\n---\n\n".join(objection_texts)
    
    prompt = f"""请根据以下投票回复，简述异议原因（1-2 句话）。

投票主题: {vote.get('subject', '')}

异议内容:
{content}

输出 JSON 格式：
{{"objection_summary": "xxx 提出 -1，原因是..."}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("objection_summary", "")
    except Exception as e:
        print(f"Error summarizing objection for '{vote.get('subject', '')}': {e}")
        return ""


def summarize_jira(client: OpenAI, jira_titles: list[str]) -> str:
    """Generate summary for JIRA issues."""
    if not jira_titles:
        return "本周无新建 JIRA。"
    
    titles_text = "\n".join(f"- {t}" for t in jira_titles[:50])  # Limit to 50 titles
    
    prompt = f"""请根据以下 JIRA 邮件标题列表，生成 2-3 句话的整体摘要，概括本周 JIRA 主要涉及哪些方面。

JIRA 标题列表:
{titles_text}

输出 JSON 格式：
{{"jira_summary": "本周 JIRA 主要集中在..."}}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("jira_summary", "")
    except Exception as e:
        print(f"Error summarizing JIRA: {e}")
        return "JIRA 摘要生成失败"


def main():
    """Main entry point."""
    # Load threads data
    with open("threads.json", "r", encoding="utf-8") as f:
        threads = json.load(f)
    
    client = create_client()
    
    # Summarize discussions (top 10 by reply count)
    print("Summarizing discussions...")
    discussions = threads.get("discussions", [])[:10]
    for i, discussion in enumerate(discussions):
        print(f"  [{i+1}/{len(discussions)}] {discussion.get('subject', '')[:50]}...")
        summary = summarize_discussion(client, discussion)
        discussion["llm_summary"] = summary
        # Remove full emails to reduce file size
        discussion.pop("emails", None)
    threads["discussions"] = discussions
    
    # Summarize vote objections
    print("Summarizing vote objections...")
    for vote in threads.get("votes", []):
        if vote.get("has_objection"):
            print(f"  Processing objection for: {vote.get('subject', '')[:50]}...")
            vote["objection_summary"] = summarize_objection(client, vote)
        vote.pop("objection_emails", None)  # Remove full emails
    
    # Summarize JIRA
    print("Summarizing JIRA...")
    threads["jira_summary"] = summarize_jira(client, threads.get("jira_titles", []))
    
    # Save summary
    with open("summary.json", "w", encoding="utf-8") as f:
        json.dump(threads, f, ensure_ascii=False, indent=2)
    
    print("Summary saved to summary.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test locally (requires API key)**

```bash
export OPENAI_BASE_URL="your-base-url"
export OPENAI_API_KEY="your-api-key"
python scripts/flink-dev/generate_summary.py
# Expected: Creates summary.json with LLM-generated summaries
```

- [ ] **Step 3: Commit**

```bash
git add scripts/flink-dev/generate_summary.py
git commit -m "feat(flink-dev): add LLM summarization for discussions/votes/JIRA"
```

---

## Chunk 4: Report Generation

### Task 5: Create HTML report generator

**Files:**
- Create: `scripts/flink-dev/generate_report.py`
- Create: `assets/flink-dev/style.css`

- [ ] **Step 1: Create style.css**

```css
/* Flink Weekly Report Styles */
:root {
    --primary-color: #e6526f;
    --text-color: #333;
    --bg-color: #f8f9fa;
    --border-color: #dee2e6;
    --success-color: #28a745;
    --warning-color: #ffc107;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    line-height: 1.6;
    color: var(--text-color);
    background: var(--bg-color);
}

.container {
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
    background: white;
    min-height: 100vh;
}

header {
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 2px solid var(--primary-color);
}

header h1 {
    color: var(--primary-color);
    font-size: 1.8rem;
    margin-bottom: 0.5rem;
}

.date-range {
    color: #666;
    font-size: 1rem;
}

section {
    margin-bottom: 2rem;
}

section h2 {
    font-size: 1.3rem;
    color: var(--text-color);
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border-color);
}

/* Announcements */
.announcements ul {
    list-style: none;
}

.announcements li {
    padding: 0.5rem 0;
    border-bottom: 1px solid #eee;
}

.announcements a {
    color: var(--primary-color);
    text-decoration: none;
}

.announcements a:hover {
    text-decoration: underline;
}

/* Votes */
.vote-item {
    padding: 1rem;
    margin-bottom: 1rem;
    background: #fafafa;
    border-radius: 8px;
    border-left: 4px solid var(--success-color);
}

.vote-item.has-objection {
    border-left-color: var(--warning-color);
}

.vote-item h3 {
    font-size: 1rem;
    margin-bottom: 0.5rem;
}

.vote-item h3 a {
    color: var(--text-color);
    text-decoration: none;
}

.vote-item h3 a:hover {
    color: var(--primary-color);
}

.vote-item .status {
    display: inline-block;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.85rem;
    margin-bottom: 0.5rem;
}

.vote-item .status.passed {
    background: #d4edda;
    color: #155724;
}

.vote-item .status.warning {
    background: #fff3cd;
    color: #856404;
}

.vote-item .objection {
    margin-top: 0.5rem;
    padding: 0.5rem;
    background: #fff3cd;
    border-radius: 4px;
    font-size: 0.9rem;
}

/* Discussions */
.discussion-item {
    padding: 1rem;
    margin-bottom: 1rem;
    background: #fafafa;
    border-radius: 8px;
}

.discussion-item h3 {
    font-size: 1rem;
    margin-bottom: 0.5rem;
}

.discussion-item h3 a {
    color: var(--text-color);
    text-decoration: none;
}

.discussion-item h3 a:hover {
    color: var(--primary-color);
}

.discussion-item .meta {
    font-size: 0.85rem;
    color: #666;
    margin-bottom: 0.5rem;
}

.discussion-item .summary {
    margin-bottom: 0.5rem;
}

.discussion-item .key-points {
    padding-left: 1rem;
    border-left: 3px solid var(--border-color);
    font-size: 0.9rem;
}

.discussion-item .key-points p {
    margin-bottom: 0.3rem;
}

.discussion-item .conclusion {
    margin-top: 0.5rem;
    font-style: italic;
    color: #555;
}

/* JIRA */
.jira p {
    margin-bottom: 0.5rem;
}

.jira-summary {
    padding: 1rem;
    background: #fafafa;
    border-radius: 8px;
}

/* Footer */
footer {
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border-color);
    text-align: center;
    color: #999;
    font-size: 0.85rem;
}

/* Index page */
.month {
    margin-bottom: 1.5rem;
}

.month h2 {
    font-size: 1.1rem;
    margin-bottom: 0.5rem;
}

.month ul {
    list-style: none;
    padding-left: 1rem;
}

.month li {
    padding: 0.3rem 0;
}

.month a {
    color: var(--primary-color);
    text-decoration: none;
}

.month a:hover {
    text-decoration: underline;
}
```

- [ ] **Step 2: Create generate_report.py**

```python
#!/usr/bin/env python3
"""Generate HTML report from summary."""

import json
import os
from pathlib import Path


GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "https://example.github.io/daily-reports")


def load_summary() -> dict:
    """Load summary data."""
    with open("summary.json", "r", encoding="utf-8") as f:
        return json.load(f)


def render_announcements(announcements: list) -> str:
    """Render announcements section."""
    if not announcements:
        return '<p class="empty">本周无公告</p>'
    
    items = "\n".join(
        f'<li><a href="{a["link"]}">{a["subject"]}</a></li>'
        for a in announcements
    )
    return f"<ul>{items}</ul>"


def render_votes(votes: list) -> str:
    """Render votes section."""
    if not votes:
        return '<p class="empty">本周无投票</p>'
    
    html_parts = []
    for vote in votes:
        has_objection = vote.get("has_objection", False)
        css_class = "vote-item has-objection" if has_objection else "vote-item"
        
        status_html = ""
        if has_objection:
            status_html = '<span class="status warning">⚠️ 有异议</span>'
        else:
            status_html = '<span class="status passed">✅ 已通过</span>'
        
        objection_html = ""
        if has_objection and vote.get("objection_summary"):
            objection_html = f'<p class="objection">{vote["objection_summary"]}</p>'
        
        html_parts.append(f'''
        <article class="{css_class}">
            <h3><a href="{vote["link"]}">{vote["subject"]}</a></h3>
            {status_html}
            {objection_html}
        </article>''')
    
    return "\n".join(html_parts)


def render_discussions(discussions: list) -> str:
    """Render discussions section."""
    if not discussions:
        return '<p class="empty">本周无讨论</p>'
    
    html_parts = []
    for disc in discussions:
        llm_summary = disc.get("llm_summary", {})
        summary = llm_summary.get("summary", "")
        key_points = llm_summary.get("key_points", [])
        conclusion = llm_summary.get("conclusion", "")
        
        key_points_html = ""
        if key_points:
            points = "\n".join(
                f'<p><strong>@{p.get("author", "")}:</strong> {p.get("point", "")}</p>'
                for p in key_points
            )
            key_points_html = f'<div class="key-points">{points}</div>'
        
        conclusion_html = ""
        if conclusion:
            conclusion_html = f'<p class="conclusion">{conclusion}</p>'
        
        html_parts.append(f'''
        <article class="discussion-item">
            <h3><a href="{disc["link"]}">{disc["subject"]}</a></h3>
            <p class="meta">{disc.get("reply_count", 0)} 条回复 · {len(disc.get("participants", []))} 位参与者</p>
            <p class="summary">{summary}</p>
            {key_points_html}
            {conclusion_html}
        </article>''')
    
    return "\n".join(html_parts)


def render_jira(jira_count: int, jira_summary: str) -> str:
    """Render JIRA section."""
    return f'''
    <p>本周新建 <strong>{jira_count}</strong> 个 Issue</p>
    <div class="jira-summary">
        <p>{jira_summary}</p>
    </div>'''


def generate_html(summary: dict) -> str:
    """Generate full HTML report."""
    week = summary.get("week", "")
    date_range = summary.get("date_range", {})
    start = date_range.get("start", "")
    end = date_range.get("end", "")
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flink 社区周报 | {week}</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Flink 社区周报 | {week}</h1>
            <p class="date-range">{start} ~ {end}</p>
        </header>

        <section class="announcements">
            <h2>📢 公告</h2>
            {render_announcements(summary.get("announcements", []))}
        </section>

        <section class="votes">
            <h2>🗳️ 投票</h2>
            {render_votes(summary.get("votes", []))}
        </section>

        <section class="discussions">
            <h2>💬 讨论</h2>
            {render_discussions(summary.get("discussions", []))}
        </section>

        <section class="jira">
            <h2>🎫 JIRA</h2>
            {render_jira(summary.get("jira_count", 0), summary.get("jira_summary", ""))}
        </section>

        <footer>
            <p>Generated by Flink Weekly Report System</p>
        </footer>
    </div>
</body>
</html>'''


def update_index(week: str):
    """Update index.html with report list."""
    reports_dir = Path("docs/flink-dev/reports")
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all reports
    reports = sorted([f.stem for f in reports_dir.glob("*.html")], reverse=True)
    
    # Group by year
    years = {}
    for w in reports:
        year = w.split("-W")[0]
        if year not in years:
            years[year] = []
        years[year].append(w)
    
    # Generate HTML
    sections = ""
    for year, weeks in sorted(years.items(), reverse=True):
        items = "".join(f'<li><a href="reports/{w}.html">{w}</a></li>' for w in sorted(weeks, reverse=True))
        sections += f'<section class="month"><h2>📅 {year}</h2><ul>{items}</ul></section>'
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Flink 社区周报</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Flink 社区周报</h1>
            <p>Apache Flink dev 邮件列表周报归档</p>
        </header>
        {sections if sections else '<p>暂无报告</p>'}
    </div>
</body>
</html>'''
    
    with open("docs/flink-dev/index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Index updated: docs/flink-dev/index.html")


def main():
    """Main entry point."""
    summary = load_summary()
    week = summary.get("week", "")
    
    # Generate HTML
    html = generate_html(summary)
    
    # Save report
    output_dir = Path("docs/flink-dev/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{week}.html"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved to {output_path}")
    
    # Update index
    update_index(week)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Commit**

```bash
mkdir -p assets/flink-dev
git add assets/flink-dev/style.css scripts/flink-dev/generate_report.py
git commit -m "feat(flink-dev): add HTML report generation"
```

---

## Chunk 5: DingTalk Push

### Task 6: Create DingTalk sender

**Files:**
- Create: `scripts/flink-dev/send_dingtalk.py`

- [ ] **Step 1: Create send_dingtalk.py**

```python
#!/usr/bin/env python3
"""Send weekly report to DingTalk."""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse

import requests


GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "https://example.github.io/daily-reports")
MAX_DISCUSSIONS = 5  # Limit discussions in DingTalk message


def load_summary() -> dict:
    """Load summary data."""
    with open("summary.json", "r", encoding="utf-8") as f:
        return json.load(f)


def generate_sign(secret: str) -> tuple[str, str]:
    """Generate DingTalk signature."""
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode("utf-8")
    string_to_sign = f"{timestamp}\n{secret}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def build_message(summary: dict) -> dict:
    """Build DingTalk markdown message."""
    week = summary.get("week", "")
    date_range = summary.get("date_range", {})
    start = date_range.get("start", "")
    end = date_range.get("end", "")
    
    # Announcements
    announcements = summary.get("announcements", [])
    announce_text = ""
    if announcements:
        announce_text = f"📢 **公告** ({len(announcements)})\n"
        for a in announcements:
            announce_text += f"- {a['subject']} [🔗]({a['link']})\n"
    else:
        announce_text = "📢 **公告** (0)\n- 本周无公告\n"
    
    # Votes
    votes = summary.get("votes", [])
    vote_text = ""
    if votes:
        vote_text = f"🗳️ **投票** ({len(votes)})\n"
        for v in votes:
            status = "⚠️ 有异议" if v.get("has_objection") else "✅ 已通过"
            vote_text += f"- {v['subject']} → {status} [🔗]({v['link']})\n"
            if v.get("has_objection") and v.get("objection_summary"):
                vote_text += f"  {v['objection_summary']}\n"
    else:
        vote_text = "🗳️ **投票** (0)\n- 本周无投票\n"
    
    # Discussions (top N)
    discussions = summary.get("discussions", [])[:MAX_DISCUSSIONS]
    discuss_text = ""
    if discussions:
        discuss_text = f"💬 **讨论** ({len(summary.get('discussions', []))})\n\n"
        for i, d in enumerate(discussions, 1):
            llm_summary = d.get("llm_summary", {})
            summary_text = llm_summary.get("summary", "")
            
            discuss_text += f"**{i}. {d['subject']}** [🔗]({d['link']})\n"
            discuss_text += f"{summary_text}\n\n"
    else:
        discuss_text = "💬 **讨论** (0)\n- 本周无讨论\n"
    
    # JIRA
    jira_count = summary.get("jira_count", 0)
    jira_summary = summary.get("jira_summary", "")
    jira_text = f"🎫 **JIRA**: 本周新建 {jira_count} 个\n{jira_summary}\n"
    
    # Report link
    report_url = f"{GITHUB_PAGES_URL}/flink-dev/reports/{week}.html"
    
    markdown_content = f"""## Flink 社区周报 ({start} ~ {end})

{announce_text}
{vote_text}
{discuss_text}
{jira_text}
🔗 [查看完整报告]({report_url})"""

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"Flink 社区周报 ({week})",
            "text": markdown_content
        }
    }


def send_dingtalk(webhook: str, secret: str, message: dict) -> bool:
    """Send message to DingTalk."""
    timestamp, sign = generate_sign(secret)
    url = f"{webhook}&timestamp={timestamp}&sign={sign}"
    
    headers = {"Content-Type": "application/json"}
    
    try:
        resp = requests.post(url, json=message, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get("errcode") == 0:
            print("DingTalk message sent successfully")
            return True
        else:
            print(f"DingTalk error: {result}")
            return False
    except Exception as e:
        print(f"DingTalk request failed: {e}")
        return False


def main():
    """Main entry point."""
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    secret = os.environ.get("DINGTALK_SECRET")
    
    if not webhook or not secret:
        print("Error: DINGTALK_WEBHOOK or DINGTALK_SECRET not set")
        sys.exit(1)
    
    summary = load_summary()
    message = build_message(summary)
    
    # Save message for debugging
    with open("dingtalk_message.json", "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)
    print("Message saved to dingtalk_message.json")
    
    # Send to DingTalk
    success = send_dingtalk(webhook, secret, message)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add scripts/flink-dev/send_dingtalk.py
git commit -m "feat(flink-dev): add DingTalk push"
```

---

## Chunk 6: GitHub Actions Workflow

### Task 7: Create GitHub Actions workflow

**Files:**
- Create: `.github/workflows/flink-dev-weekly-report.yml`

- [ ] **Step 1: Create workflow file**

```yaml
name: Flink Dev Weekly Report

on:
  schedule:
    - cron: '0 1 * * 4'  # UTC 01:00 Thursday = Beijing 09:00 Thursday
  workflow_dispatch:
    inputs:
      week:
        description: '报告周数 (YYYY-Www), 留空则为上一周'
        required: false
        default: ''

permissions:
  contents: write

jobs:
  generate-report:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests aiohttp openai

      - name: Calculate week
        id: week
        run: |
          if [ -n "${{ github.event.inputs.week }}" ]; then
            echo "week=${{ github.event.inputs.week }}" >> $GITHUB_OUTPUT
          else
            echo "week=$(date -d 'last monday - 7 days' +%G-W%V)" >> $GITHUB_OUTPUT
          fi

      - name: Fetch emails
        env:
          REPORT_WEEK: ${{ steps.week.outputs.week }}
        run: python scripts/flink-dev/fetch_emails.py

      - name: Classify emails
        run: python scripts/flink-dev/classify_emails.py

      - name: Generate summary with LLM
        env:
          OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: python scripts/flink-dev/generate_summary.py

      - name: Generate reports
        env:
          GITHUB_PAGES_URL: https://${{ github.repository_owner }}.github.io/${{ github.event.repository.name }}
        run: python scripts/flink-dev/generate_report.py

      - name: Send to DingTalk
        env:
          DINGTALK_WEBHOOK: ${{ secrets.DINGTALK_WEBHOOK }}
          DINGTALK_SECRET: ${{ secrets.DINGTALK_SECRET }}
          GITHUB_PAGES_URL: https://${{ github.repository_owner }}.github.io/${{ github.event.repository.name }}
        run: python scripts/flink-dev/send_dingtalk.py

      - name: Deploy to pages branch
        run: |
          # Save flink-dev docs to temp
          cp -r docs/flink-dev /tmp/flink-dev-output
          mkdir -p /tmp/flink-dev-output/assets
          cp assets/flink-dev/style.css /tmp/flink-dev-output/assets/

          # Checkout pages branch
          git fetch origin pages || true
          if git show-ref --verify --quiet refs/remotes/origin/pages; then
            git checkout pages
          else
            git checkout --orphan pages
            git rm -rf . || true
          fi

          # Merge flink-dev content (preserve other directories)
          rm -rf flink-dev || true
          cp -r /tmp/flink-dev-output flink-dev

          # Update root index.html
          cat > index.html << 'INDEXEOF'
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Reports</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 600px; margin: 2rem auto; padding: 1rem; }
        h1 { color: #1a73e8; }
        .links { display: flex; gap: 1rem; margin-top: 2rem; flex-wrap: wrap; }
        a { display: block; padding: 1.5rem 2rem; background: #f8f9fa; border-radius: 8px; text-decoration: none; color: #1a73e8; border: 1px solid #dadce0; }
        a:hover { background: #e8f0fe; }
    </style>
</head>
<body>
    <h1>Daily Reports</h1>
    <p>Select a report type:</p>
    <div class="links">
        <a href="fluss-github/">🌊 Fluss GitHub</a>
        <a href="data-ai/">📊 Data+AI</a>
        <a href="flink-dev/">🔥 Flink Dev</a>
    </div>
</body>
</html>
INDEXEOF

          # Commit and push
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add -A
          git diff --staged --quiet || git commit -m "chore: add flink-dev weekly report for ${{ steps.week.outputs.week }}"
          git push origin pages
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/flink-dev-weekly-report.yml
git commit -m "feat(flink-dev): add GitHub Actions workflow"
```

---

## Chunk 7: Integration & Test

### Task 8: Integration test

- [ ] **Step 1: Run full pipeline locally**

```bash
cd /Users/wuchong/Workspace/Fluss/daily-reports

# Set environment variables
export OPENAI_BASE_URL="your-base-url"
export OPENAI_API_KEY="your-api-key"
export DINGTALK_WEBHOOK="your-webhook"
export DINGTALK_SECRET="your-secret"
export GITHUB_PAGES_URL="https://wuchong.github.io/daily-reports"

# Run pipeline
python scripts/flink-dev/fetch_emails.py
python scripts/flink-dev/classify_emails.py
python scripts/flink-dev/generate_summary.py
python scripts/flink-dev/generate_report.py
python scripts/flink-dev/send_dingtalk.py

# Check outputs
ls -la raw_emails.json threads.json summary.json dingtalk_message.json
ls -la docs/flink-dev/
```

- [ ] **Step 2: Trigger GitHub Actions manually**

```bash
# Push all changes
git push origin main

# Trigger workflow manually via GitHub UI or gh CLI
gh workflow run flink-dev-weekly-report.yml
```

- [ ] **Step 3: Verify outputs**

1. Check GitHub Actions run status
2. Verify DingTalk message received
3. Check GitHub Pages deployment at `/flink-dev/`

### Task 9: Final commit

- [ ] **Step 1: Add all remaining files**

```bash
git add -A
git diff --staged --quiet || git commit -m "chore: finalize flink-dev weekly report system"
git push origin main
```
