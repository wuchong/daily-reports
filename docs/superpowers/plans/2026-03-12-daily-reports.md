# Daily Reports Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build automated daily report system for apache/fluss repo with DingTalk notification and GitHub Pages archive.

**Architecture:** Hybrid approach - Shell script collects GitHub data via gh CLI, Claude API generates summaries, Python script generates HTML reports and DingTalk messages, GitHub Actions orchestrates daily runs.

**Tech Stack:** Bash, Python 3.11, GitHub Actions, Claude API, gh CLI

---

## File Structure

```
daily-reports/
├── .github/workflows/daily-report.yml    # GitHub Actions workflow
├── scripts/
│   ├── collect_data.sh                   # Data collection via gh CLI
│   └── generate_report.py                # Report generation
├── prompts/
│   └── summarize.md                      # Claude prompt template
├── docs/
│   ├── index.html                        # Archive homepage
│   ├── reports/                          # Daily report HTMLs
│   └── assets/
│       └── style.css                     # Shared styles
└── .gitignore
```

---

## Chunk 1: Data Collection Script

### Task 1: Create collect_data.sh

**Files:**
- Create: `scripts/collect_data.sh`

- [ ] **Step 1: Create scripts directory**

```bash
mkdir -p scripts
```

- [ ] **Step 2: Create collect_data.sh with date handling**

```bash
#!/bin/bash
set -e

# Input: DATE (YYYY-MM-DD), defaults to yesterday
DATE=${1:-$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)}
REPO="apache/fluss"
OUTPUT_FILE="raw_data.json"

echo "Collecting data for $REPO since $DATE..."
```

- [ ] **Step 3: Add gh CLI commands for issues**

```bash
# New issues
NEW_ISSUES=$(gh issue list --repo $REPO --state all --limit 50 \
  --search "created:>=$DATE" \
  --json number,title,state,labels,url,createdAt,author 2>/dev/null || echo "[]")

# Closed issues
CLOSED_ISSUES=$(gh issue list --repo $REPO --state closed --limit 30 \
  --search "closed:>=$DATE" \
  --json number,title,closedAt,author,url,labels 2>/dev/null || echo "[]")
```

- [ ] **Step 4: Add gh CLI commands for PRs**

```bash
# Open PRs
OPEN_PRS=$(gh pr list --repo $REPO --state open --limit 50 \
  --search "created:>=$DATE" \
  --json number,title,labels,url,createdAt,author 2>/dev/null || echo "[]")

# Merged PRs
MERGED_PRS=$(gh pr list --repo $REPO --state merged --limit 30 \
  --search "merged:>=$DATE" \
  --json number,title,mergedAt,author,url,labels 2>/dev/null || echo "[]")
```

- [ ] **Step 5: Add gh API commands for comments**

```bash
# Issue comments
ISSUE_COMMENTS=$(gh api "repos/$REPO/issues/comments?since=${DATE}T00:00:00Z&per_page=100" \
  --jq '[.[] | {issue_url, body, user: .user.login, created_at}]' 2>/dev/null || echo "[]")

# PR review comments
PR_COMMENTS=$(gh api "repos/$REPO/pulls/comments?since=${DATE}T00:00:00Z&per_page=100" \
  --jq '[.[] | {pull_request_url, body, user: .user.login, path, created_at}]' 2>/dev/null || echo "[]")
```

- [ ] **Step 6: Assemble JSON output**

```bash
# Assemble JSON
cat > $OUTPUT_FILE << EOF
{
  "date": "$DATE",
  "repo": "$REPO",
  "new_issues": $NEW_ISSUES,
  "closed_issues": $CLOSED_ISSUES,
  "open_prs": $OPEN_PRS,
  "merged_prs": $MERGED_PRS,
  "issue_comments": $ISSUE_COMMENTS,
  "pr_review_comments": $PR_COMMENTS
}
EOF

echo "Data saved to $OUTPUT_FILE"
```

- [ ] **Step 7: Make script executable and commit**

```bash
chmod +x scripts/collect_data.sh
git add scripts/collect_data.sh
git commit -m "feat: add data collection script"
```

---

## Chunk 2: Claude Prompt Template

### Task 2: Create summarize.md prompt

**Files:**
- Create: `prompts/summarize.md`

- [ ] **Step 1: Create prompts directory**

```bash
mkdir -p prompts
```

- [ ] **Step 2: Create summarize.md**

```markdown
# GitHub Daily Report Summarizer

You are analyzing GitHub repository activity data. Generate a structured summary in Chinese.

## Input

The following JSON contains today's GitHub activity for apache/fluss:

```json
{{RAW_DATA}}
```

## Output Format

Generate a JSON response with this exact structure:

```json
{
  "highlights": [
    "🎉 描述重要的 PR 合并或功能",
    "🐛 描述重要的 bug 修复",
    "✨ 描述其他亮点"
  ],
  "critical_issues": [
    "⚠️ 描述需要紧急关注的问题"
  ],
  "issue_comments_summary": "Issue 讨论的主要内容摘要...",
  "pr_review_summary": "PR Review 的主要关注点摘要..."
}
```

## Guidelines

1. **highlights**: 3-5 条核心要点
   - 优先展示已合并的重要 PR
   - 包含重要 bug 修复
   - 使用 emoji: 🎉(合并) 🐛(bug) ✨(新功能) 🚀(性能) 📚(文档)

2. **critical_issues**: 需要关注的问题
   - 查找包含 bug, critical, P0, P1, high-priority 标签的 issue
   - 如果没有则返回空数组

3. **issue_comments_summary**: 50-100字摘要
   - 总结主要讨论话题
   - 如果没有评论则返回 "今日无新评论"

4. **pr_review_summary**: 50-100字摘要
   - 总结 code review 的主要关注点
   - 如果没有评论则返回 "今日无新 Review 评论"

Only output valid JSON, no other text.
```

- [ ] **Step 3: Commit prompt file**

```bash
git add prompts/summarize.md
git commit -m "feat: add Claude summarization prompt"
```

---

## Chunk 3: Report Generation Script

### Task 3: Create generate_report.py

**Files:**
- Create: `scripts/generate_report.py`

- [ ] **Step 1: Create Python script with imports and constants**

```python
#!/usr/bin/env python3
"""Generate HTML report and DingTalk message from GitHub activity data."""

import json
import os
from datetime import datetime
from pathlib import Path

REPO = "apache/fluss"
REPO_NAME = "Fluss"
GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "https://your-username.github.io/daily-reports")
```

- [ ] **Step 2: Add data loading functions**

```python
def load_json(filepath: str) -> dict:
    """Load JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_json(data: dict, filepath: str):
    """Save data as JSON file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
```

- [ ] **Step 3: Add HTML report generation function**

```python
def generate_html_report(raw_data: dict, summary: dict, output_path: str):
    """Generate full HTML report."""
    date = raw_data['date']
    
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
                {"".join(f'<li>{h}</li>' for h in summary.get('highlights', ['暂无']))}
            </ul>
        </section>
        
        <section class="critical">
            <h2>⚠️ 重点关注</h2>
            {generate_critical_section(summary.get('critical_issues', []))}
        </section>
        
        <section class="new-items">
            <h2>📝 新建 Issue/PR</h2>
            <h3>Issues</h3>
            {generate_item_list(raw_data.get('new_issues', []), 'issue')}
            <h3>Pull Requests</h3>
            {generate_item_list(raw_data.get('open_prs', []), 'pr')}
        </section>
        
        <section class="activity">
            <h2>💬 Issue/PR 动态</h2>
            <h3>Issue 讨论</h3>
            <p>{summary.get('issue_comments_summary', '今日无新评论')}</p>
            <h3>PR Review</h3>
            <p>{summary.get('pr_review_summary', '今日无新 Review 评论')}</p>
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
```

- [ ] **Step 4: Add helper functions for HTML generation**

```python
def generate_critical_section(critical_issues: list) -> str:
    """Generate critical issues section."""
    if not critical_issues:
        return '<p class="no-issues">✅ 今日无重大问题</p>'
    return '<ul class="critical-list">' + ''.join(f'<li>{issue}</li>' for issue in critical_issues) + '</ul>'


def generate_item_list(items: list, item_type: str) -> str:
    """Generate HTML list for issues or PRs."""
    if not items:
        return '<p class="empty">暂无</p>'
    
    html_items = []
    for item in items:
        number = item.get('number', '')
        title = item.get('title', '')
        url = item.get('url', '')
        author = item.get('author', {}).get('login', 'unknown') if isinstance(item.get('author'), dict) else item.get('author', 'unknown')
        labels = ', '.join(l.get('name', '') for l in item.get('labels', []) if isinstance(l, dict))
        
        label_html = f'<span class="labels">{labels}</span>' if labels else ''
        html_items.append(f'<li><a href="{url}">#{number}</a> {title} <span class="author">@{author}</span> {label_html}</li>')
    
    return '<ul>' + ''.join(html_items) + '</ul>'
```

- [ ] **Step 5: Add DingTalk message generation**

```python
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
```

- [ ] **Step 6: Add main function**

```python
def main():
    """Main entry point."""
    # Load data
    raw_data = load_json('raw_data.json')
    summary = load_json('summary.json')
    
    date = raw_data['date']
    
    # Generate HTML report
    html_path = f'docs/reports/{date}.html'
    generate_html_report(raw_data, summary, html_path)
    
    # Generate DingTalk message
    report_url = f"{GITHUB_PAGES_URL}/reports/{date}.html"
    dingtalk_msg = generate_dingtalk_message(raw_data, summary, report_url)
    save_json(dingtalk_msg, 'dingtalk_message.json')
    print("DingTalk message saved to dingtalk_message.json")
    
    # Update index.html
    update_index_html()


if __name__ == '__main__':
    main()
```

- [ ] **Step 7: Add index.html update function**

```python
def update_index_html():
    """Update the archive index page."""
    reports_dir = Path('docs/reports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all report files
    report_files = sorted(reports_dir.glob('*.html'), reverse=True)
    
    # Group by month
    months = {}
    for f in report_files:
        date_str = f.stem  # YYYY-MM-DD
        month = date_str[:7]  # YYYY-MM
        if month not in months:
            months[month] = []
        months[month].append(date_str)
    
    # Generate HTML
    sections = []
    for month, dates in sorted(months.items(), reverse=True):
        items = ''.join(f'<li><a href="reports/{d}.html">{d}</a></li>' for d in dates)
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
</head>
<body>
    <div class="container">
        <header>
            <h1>🌊 Fluss Daily Reports</h1>
            <p>apache/fluss 每日动态归档</p>
        </header>
        {"".join(sections) if sections else '<p>暂无报告</p>'}
    </div>
</body>
</html>'''
    
    with open('docs/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Index updated: docs/index.html")
```

- [ ] **Step 8: Make script executable and commit**

```bash
chmod +x scripts/generate_report.py
git add scripts/generate_report.py
git commit -m "feat: add report generation script"
```

---

## Chunk 4: CSS Styles

### Task 4: Create style.css

**Files:**
- Create: `docs/assets/style.css`

- [ ] **Step 1: Create assets directory**

```bash
mkdir -p docs/assets docs/reports
```

- [ ] **Step 2: Create style.css**

```css
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent: #58a6ff;
    --border: #30363d;
    --success: #3fb950;
    --warning: #d29922;
    --danger: #f85149;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
}

.container {
    max-width: 900px;
    margin: 0 auto;
    padding: 2rem;
}

header {
    text-align: center;
    margin-bottom: 2rem;
    padding-bottom: 1rem;
    border-bottom: 1px solid var(--border);
}

header h1 {
    font-size: 2rem;
    margin-bottom: 0.5rem;
}

header .date, header .repo {
    color: var(--text-secondary);
}

header a {
    color: var(--accent);
    text-decoration: none;
}

.stats {
    display: flex;
    justify-content: center;
    gap: 1.5rem;
    flex-wrap: wrap;
    margin-bottom: 2rem;
}

.stat {
    background: var(--bg-secondary);
    padding: 0.75rem 1.25rem;
    border-radius: 8px;
    border: 1px solid var(--border);
}

section {
    margin-bottom: 2rem;
    background: var(--bg-secondary);
    padding: 1.5rem;
    border-radius: 8px;
    border: 1px solid var(--border);
}

section h2 {
    margin-bottom: 1rem;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
}

section h3 {
    margin: 1rem 0 0.5rem;
    color: var(--text-secondary);
    font-size: 1rem;
}

ul {
    list-style: none;
}

li {
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border);
}

li:last-child {
    border-bottom: none;
}

li a {
    color: var(--accent);
    text-decoration: none;
    font-weight: 500;
}

.author {
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.labels {
    background: var(--bg-primary);
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    color: var(--text-secondary);
}

.critical-list li {
    color: var(--warning);
}

.no-issues {
    color: var(--success);
}

.empty {
    color: var(--text-secondary);
    font-style: italic;
}

footer {
    text-align: center;
    color: var(--text-secondary);
    margin-top: 2rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
}

footer a {
    color: var(--accent);
    text-decoration: none;
}

/* Month sections in index */
.month {
    margin-bottom: 1rem;
}

.month h2 {
    cursor: pointer;
}

@media (max-width: 600px) {
    .container {
        padding: 1rem;
    }
    
    .stats {
        flex-direction: column;
        align-items: center;
    }
}
```

- [ ] **Step 3: Commit CSS file**

```bash
git add docs/assets/style.css
git commit -m "feat: add CSS styles"
```

---

## Chunk 5: GitHub Actions Workflow

### Task 5: Create daily-report.yml

**Files:**
- Create: `.github/workflows/daily-report.yml`

- [ ] **Step 1: Create workflow directory**

```bash
mkdir -p .github/workflows
```

- [ ] **Step 2: Create workflow file**

```yaml
name: Daily Report

on:
  schedule:
    - cron: '0 1 * * *'  # UTC 01:00 = Beijing 09:00
  workflow_dispatch:
    inputs:
      date:
        description: '报告日期 (YYYY-MM-DD), 留空则为昨天'
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
      
      - name: Calculate date
        id: date
        run: |
          if [ -n "${{ github.event.inputs.date }}" ]; then
            echo "date=${{ github.event.inputs.date }}" >> $GITHUB_OUTPUT
          else
            echo "date=$(date -d 'yesterday' +%Y-%m-%d)" >> $GITHUB_OUTPUT
          fi
      
      - name: Collect GitHub data
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: bash scripts/collect_data.sh ${{ steps.date.outputs.date }}
      
      - name: Generate summary with Claude
        uses: anthropic/claude-code-action@v1
        env:
          ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
        with:
          prompt: |
            Read the file raw_data.json and follow the instructions in prompts/summarize.md.
            Save the output to summary.json.
      
      - name: Generate reports
        env:
          GITHUB_PAGES_URL: https://${{ github.repository_owner }}.github.io/${{ github.event.repository.name }}
        run: python scripts/generate_report.py
      
      - name: Send to DingTalk
        if: success()
        run: |
          curl -s -X POST "${{ secrets.DINGTALK_WEBHOOK }}" \
            -H "Content-Type: application/json" \
            -d @dingtalk_message.json
      
      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add docs/
          git diff --staged --quiet || git commit -m "chore: add daily report for ${{ steps.date.outputs.date }}"
          git push
```

- [ ] **Step 3: Commit workflow file**

```bash
git add .github/workflows/daily-report.yml
git commit -m "feat: add GitHub Actions workflow"
```

---

## Chunk 6: Project Setup

### Task 6: Create .gitignore and initial docs

**Files:**
- Create: `.gitignore`
- Create: `docs/index.html` (initial)

- [ ] **Step 1: Create .gitignore**

```gitignore
# Generated files
raw_data.json
summary.json
dingtalk_message.json

# Python
__pycache__/
*.pyc
.venv/

# OS
.DS_Store

# IDE
.idea/
.vscode/
```

- [ ] **Step 2: Create initial index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌊 Fluss Daily Reports</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>🌊 Fluss Daily Reports</h1>
            <p>apache/fluss 每日动态归档</p>
        </header>
        <p>暂无报告，等待首次运行...</p>
    </div>
</body>
</html>
```

- [ ] **Step 3: Commit all setup files**

```bash
git add .gitignore docs/index.html
git commit -m "chore: add gitignore and initial index"
```

---

## Chunk 7: Final Verification

### Task 7: Local testing and documentation

- [ ] **Step 1: Test collect_data.sh locally**

```bash
export GH_TOKEN=$(gh auth token)
bash scripts/collect_data.sh 2026-03-11
cat raw_data.json | head -50
```

Expected: JSON file with GitHub activity data

- [ ] **Step 2: Create mock summary.json for testing**

```json
{
  "highlights": [
    "🎉 测试高亮 1",
    "🐛 测试高亮 2"
  ],
  "critical_issues": [],
  "issue_comments_summary": "测试评论摘要",
  "pr_review_summary": "测试 Review 摘要"
}
```

- [ ] **Step 3: Test generate_report.py**

```bash
python scripts/generate_report.py
ls -la docs/reports/
cat dingtalk_message.json
```

Expected: HTML file generated, DingTalk message JSON created

- [ ] **Step 4: View generated HTML**

```bash
open docs/reports/2026-03-11.html  # macOS
# or: xdg-open docs/reports/2026-03-11.html  # Linux
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git status
git commit -m "chore: complete daily-reports project setup"
```

---

## Required GitHub Configuration

After pushing to GitHub:

1. **Enable GitHub Pages:**
   - Settings → Pages → Source: Deploy from branch
   - Branch: main, folder: /docs

2. **Add Repository Secrets:**
   - `ANTHROPIC_BASE_URL`: Your Claude API endpoint
   - `ANTHROPIC_AUTH_TOKEN`: Your Claude API token
   - `DINGTALK_WEBHOOK`: DingTalk robot webhook URL

3. **Test Workflow:**
   - Actions → Daily Report → Run workflow
   - Input a specific date or leave empty for yesterday
