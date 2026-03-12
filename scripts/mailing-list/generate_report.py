#!/usr/bin/env python3
"""Generate HTML report from summary.

Environment variables:
- PROJECT_NAME: Project display name (e.g., Flink, Iceberg, Kafka, Spark)
- PROJECT_ID: Project identifier for paths (e.g., flink-dev, iceberg-dev)
- GITHUB_PAGES_URL: Base URL for GitHub Pages
"""

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
    
    items = []
    for vote in votes:
        vote_status = vote.get("status", "in_progress")
        has_objection = vote.get("has_objection", False)
        
        # Determine display status
        if vote_status == "passed":
            status = '<span class="status passed">✅ 已通过</span>'
        elif vote_status == "failed":
            status = '<span class="status failed">❌ 未通过</span>'
        elif has_objection:
            status = '<span class="status warning">⚠️ 有异议</span>'
        else:
            status = '<span class="status in-progress">🗳️ 进行中</span>'
        
        # Show reason for failure or objection
        reason_html = ""
        if vote_status == "failed" and vote.get("fail_reason"):
            reason_html = f'<p class="fail-reason">{vote["fail_reason"]}</p>'
        elif has_objection and vote.get("objection_summary"):
            reason_html = f'<p class="objection-inline">{vote["objection_summary"]}</p>'
        
        items.append(f'<li><a href="{vote["link"]}">{vote["subject"]}</a> {status}{reason_html}</li>')
    
    items_html = "\n".join(items)
    return f'<ul class="vote-list">{items_html}</ul>'


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


def generate_html(summary: dict, project_name: str) -> str:
    """Generate full HTML report."""
    week = summary.get("week", "")
    date_range = summary.get("date_range", {})
    start = date_range.get("start", "")
    end = date_range.get("end", "")
    
    announcements = summary.get("announcements", [])
    votes = summary.get("votes", [])
    discussions = summary.get("discussions", [])
    jira_count = summary.get("jira_count", 0)
    jira_summary = summary.get("jira_summary", "")
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_name} 社区周报 | {week}</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <nav class="back-link"><a href="../index.html">← 返回列表</a></nav>
            <h1>{project_name} 社区周报 | {week}</h1>
            <p class="date-range">{start} ~ {end}</p>
        </header>

        <section class="announcements">
            <h2>📢 公告 ({len(announcements)})</h2>
            {render_announcements(announcements)}
        </section>

        <section class="votes">
            <h2>🗳️ 投票 ({len(votes)})</h2>
            {render_votes(votes)}
        </section>

        <section class="discussions">
            <h2>💬 讨论 ({len(discussions)})</h2>
            {render_discussions(discussions)}
        </section>

        <section class="jira">
            <h2>🎫 JIRA ({jira_count})</h2>
            {render_jira(jira_count, jira_summary)}
        </section>

        <footer>
            <p>Generated by {project_name} Weekly Report System</p>
        </footer>
    </div>
</body>
</html>'''


def update_index(week: str, project_id: str, project_name: str):
    """Update index.html with report list."""
    reports_dir = Path(f"docs/{project_id}/reports")
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
    <title>{project_name} 社区周报</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>{project_name} 社区周报</h1>
            <p>Apache {project_name} dev 邮件列表周报归档</p>
        </header>
        {sections if sections else '<p>暂无报告</p>'}
    </div>
</body>
</html>'''
    
    index_path = Path(f"docs/{project_id}/index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Index updated: {index_path}")


def main():
    """Main entry point."""
    project_name = os.environ.get("PROJECT_NAME", "Apache")
    project_id = os.environ.get("PROJECT_ID", "mailing-list")
    
    summary = load_summary()
    week = summary.get("week", "")
    
    # Generate HTML
    html = generate_html(summary, project_name)
    
    # Save report
    output_dir = Path(f"docs/{project_id}/reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{week}.html"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Report saved to {output_path}")
    
    # Update index
    update_index(week, project_id, project_name)


if __name__ == "__main__":
    main()
