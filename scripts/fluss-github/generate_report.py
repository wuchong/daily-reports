#!/usr/bin/env python3
"""Generate HTML report and DingTalk message from GitHub activity data."""

import json
import os
import re
from datetime import datetime
from pathlib import Path

REPO = "apache/fluss"
REPO_NAME = "Fluss"
GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "https://your-username.github.io/daily-reports")


def markdown_links_to_html(text: str) -> str:
    """Convert markdown links [text](url) to HTML <a href='url'>text</a>."""
    pattern = r'\[([^\]]+)\]\(([^)]+)\)'
    return re.sub(pattern, r'<a href="\2">\1</a>', text)


def load_json(filepath: str) -> dict:
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: dict, filepath: str):
    """Save data as JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def generate_critical_section(critical_issues: list) -> str:
    """Generate critical issues section."""
    if not critical_issues:
        return '<p class="no-issues">✅ 今日无重大问题</p>'
    items = [f'<li>{markdown_links_to_html(issue)}</li>' for issue in critical_issues]
    return '<ul class="critical-list">' + ''.join(items) + '</ul>'


def build_title_map(raw_data: dict) -> dict:
    """Build a mapping from issue/PR number to title."""
    title_map = {}
    for source in ['new_issues', 'closed_issues', 'open_prs', 'merged_prs', 'commented_issues', 'commented_prs']:
        for item in raw_data.get(source, []):
            number = item.get('number')
            title = item.get('title', '')
            if number and title:
                title_map[number] = title
    return title_map


def generate_activity_section(activity: list, item_type: str, title_map: dict = None) -> str:
    """Generate per-issue/PR activity section."""
    if not activity:
        return '<p class="empty">暂无</p>'
    
    title_map = title_map or {}
    prefix = "Issue" if item_type == "issue" else "PR"
    html_items = []
    for item in activity:
        number = item.get('number', '')
        item_title = item.get('title', '')
        url = item.get('url', '')
        comments = item.get('comments', [])
        
        # Use title from raw_data if LLM returned invalid title
        if not item_title or item_title.startswith(('Issue #', 'PR #')):
            item_title = title_map.get(number, '')
        
        comments_html = ''.join(
            f'<li><span class="author">@{c.get("user", "unknown")}</span>: {markdown_links_to_html(c.get("summary", ""))}</li>'
            for c in comments
        )
        html_items.append(f'''
        <div class="activity-item">
            <h4><a href="{url}">{prefix} #{number}</a> {item_title}</h4>
            <ul>{comments_html}</ul>
        </div>''')
    
    return ''.join(html_items)


def generate_item_list(items: list, item_type: str) -> str:
    """Generate HTML list for issues or PRs."""
    if not items:
        return '<p class="empty">暂无</p>'
    
    html_items = []
    for item in items:
        number = item.get('number', '')
        title = item.get('title', '')
        url = item.get('url', '')
        author = item.get('author', {})
        if isinstance(author, dict):
            author = author.get('login', 'unknown')
        elif not author:
            author = 'unknown'
        labels = ', '.join(l.get('name', '') for l in item.get('labels', []) if isinstance(l, dict))
        
        label_html = f'<span class="labels">{labels}</span>' if labels else ''
        html_items.append(f'<li><a href="{url}">#{number}</a> {title} <span class="author">@{author}</span> {label_html}</li>')
    
    return '<ul>' + ''.join(html_items) + '</ul>'


def generate_html_report(raw_data: dict, summary: dict, output_path: str):
    """Generate full HTML report."""
    date = raw_data['date']
    title_map = build_title_map(raw_data)
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌊 {REPO_NAME} 每日动态 - {date}</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>🌊 {REPO_NAME} 每日动态</h1>
            <p class="date">📅 {date}</p>
            <p class="repo">🔗 <a href="https://github.com/{REPO}">{REPO}</a></p>
            <nav class="back-link"><a href="../index.html">← 返回列表</a></nav>
        </header>
        
        <section class="stats">
            <div class="stat">📝 {len(raw_data.get('new_issues', []))} 新 Issues</div>
            <div class="stat">✅ {len(raw_data.get('closed_issues', []))} 关闭</div>
            <div class="stat">✨ {len(raw_data.get('open_prs', []))} 新 PRs</div>
            <div class="stat">🎉 {len(raw_data.get('merged_prs', []))} 合并</div>
        </section>
        
        <section class="highlights">
            <h2>🔥 核心要点</h2>
            <ul>
                {"".join(f'<li>{markdown_links_to_html(h)}</li>' for h in summary.get('highlights', ['暂无']))}
            </ul>
        </section>
                
        <section class="critical">
            <h2>⚠️ 重点关注</h2>
            {generate_critical_section(summary.get('critical_issues', []))}
        </section>
                
        <section class="activity">
            <h2>💬 Issue/PR 动态</h2>
            <h3>Issue 讨论</h3>
            {generate_activity_section(summary.get('issue_activity', []), 'issue', title_map)}
            <h3>PR Review</h3>
            {generate_activity_section(summary.get('pr_activity', []), 'pr', title_map)}
        </section>
                
        <section class="new-items">
            <h2>📝 新建 Issue/PR</h2>
            <h3>Issues</h3>
            {generate_item_list(raw_data.get('new_issues', []), 'issue')}
            <h3>Pull Requests</h3>
            {generate_item_list(raw_data.get('open_prs', []), 'pr')}
        </section>
                
        <section class="closed">
            <h2>✅ 关闭 Issue/PR</h2>
            <h3>已关闭 Issues</h3>
            {generate_item_list(raw_data.get('closed_issues', []), 'issue')}
            <h3>已合并 PRs</h3>
            {generate_item_list(raw_data.get('merged_prs', []), 'pr')}
        </section>
        
        <footer>
            <p>Generated by <a href="https://github.com/{REPO}">daily-reports</a></p>
        </footer>
    </div>
</body>
</html>'''
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"HTML report saved to {output_path}")


def generate_dingtalk_message(raw_data: dict, summary: dict, report_url: str) -> dict:
    """Generate DingTalk webhook message."""
    date = raw_data['date']
    
    stats = f"📊 **统计**: {len(raw_data.get('new_issues', []))} 新 Issues | {len(raw_data.get('closed_issues', []))} 关闭 | {len(raw_data.get('open_prs', []))} 新 PR | {len(raw_data.get('merged_prs', []))} 合并"
    
    highlights = summary.get('highlights', [])
    highlights_text = '\n'.join(f'- {h}' for h in highlights[:5]) if highlights else '- 今日暂无重要更新'
    
    critical = summary.get('critical_issues', [])
    critical_text = '\n'.join(f'- {c}' for c in critical) if critical else '无'
    
    markdown_content = f"""## 🌊 Fluss 每日动态 ({date})

{stats}

🔥 **核心要点**:
{highlights_text}

⚠️ **需要关注**: 
{critical_text}

🔗 [查看完整报告]({report_url})"""

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"Fluss 每日动态 ({date})",
            "text": markdown_content
        }
    }


def generate_rss_feed(reports: list[str], base_url: str) -> str:
    """Generate RSS feed XML."""
    items = []
    for date_str in reports[:20]:  # Latest 20 reports
        items.append(f'''    <item>
      <title>Fluss 每日动态 - {date_str}</title>
      <link>{base_url}/fluss-github/reports/{date_str}.html</link>
      <guid>{base_url}/fluss-github/reports/{date_str}.html</guid>
      <pubDate>{date_str}</pubDate>
    </item>''')
    
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fluss Daily Reports</title>
    <link>{base_url}/fluss-github/</link>
    <description>Apache Fluss 每日动态归档</description>
    <language>zh-CN</language>
{chr(10).join(items)}
  </channel>
</rss>'''


def update_index_html():
    """Update the archive index page and RSS feed."""
    reports_dir = Path('docs/fluss-github/reports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all report files
    report_files = sorted(reports_dir.glob('*.html'), reverse=True)
    all_dates = [f.stem for f in report_files]
    
    # Group by month
    months = {}
    for date_str in all_dates:
        month = date_str[:7]  # YYYY-MM
        if month not in months:
            months[month] = []
        months[month].append(date_str)
    
    # Generate HTML
    sections = []
    for month, dates in sorted(months.items(), reverse=True):
        items = ''.join(f'<li><a href="reports/{d}.html">{d}</a></li>' for d in sorted(dates, reverse=True))
        sections.append(f'''
        <section class="month">
            <h2>📅 {month}</h2>
            <ul>{items}</ul>
        </section>''')
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌊 Fluss Daily Reports</title>
    <link rel="stylesheet" href="assets/style.css">
    <link rel="alternate" type="application/rss+xml" title="Fluss Daily Reports RSS" href="feed.xml">
</head>
<body>
    <div class="container">
        <header>
            <h1>🌊 Fluss Daily Reports</h1>
            <p>apache/fluss 每日动态归档</p>
            <a class="rss-button" href="feed.xml" title="RSS 订阅">📡 RSS 订阅</a>
        </header>
        {"".join(sections) if sections else '<p>暂无报告</p>'}
    </div>
</body>
</html>'''
    
    with open('docs/fluss-github/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Index updated: docs/fluss-github/index.html")
    
    # Generate RSS feed
    rss = generate_rss_feed(all_dates, GITHUB_PAGES_URL)
    with open('docs/fluss-github/feed.xml', 'w', encoding='utf-8') as f:
        f.write(rss)
    print("RSS feed updated: docs/fluss-github/feed.xml")


def main():
    """Main entry point."""
    # Load data
    raw_data = load_json('raw_data.json')
    summary = load_json('summary.json')
    
    date = raw_data['date']
    
    # Generate HTML report
    html_path = f'docs/fluss-github/reports/{date}.html'
    generate_html_report(raw_data, summary, html_path)
    
    # Generate DingTalk message
    report_url = f"{GITHUB_PAGES_URL}/fluss-github/reports/{date}.html"
    dingtalk_msg = generate_dingtalk_message(raw_data, summary, report_url)
    save_json(dingtalk_msg, 'dingtalk_message.json')
    print("DingTalk message saved to dingtalk_message.json")
    
    # Update index.html
    update_index_html()


if __name__ == '__main__':
    main()
