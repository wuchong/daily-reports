# Daily Reports Design Spec

Apache Fluss 仓库每日动态报告系统，自动汇总 GitHub 活动，输出精简钉钉消息和完整 HTML 归档。

## Overview

- **Target Repo:** apache/fluss
- **Schedule:** Daily 9:00 AM Beijing time (UTC 01:00)
- **Outputs:** DingTalk message + GitHub Pages HTML archive
- **Approach:** Hybrid - Shell/Python data collection + Claude API summarization

## Architecture

```
GitHub Actions Workflow (cron: 9 AM Beijing)
    │
    ▼
Step 1: Data Collection (gh CLI)
    - New/Closed Issues, Open/Merged PRs
    - Issue Comments, PR Review Comments
    - Output: raw_data.json
    │
    ▼
Step 2: Claude API (anthropic/claude-code-action@v1)
    - Input: raw_data.json
    - Output: summary.json (核心要点, 重点关注, 动态摘要)
    │
    ▼
Step 3: Report Generation (Python)
    - Full HTML report → docs/reports/YYYY-MM-DD.html
    - DingTalk message → POST to webhook
    │
    ▼
Step 4: Publish
    - DingTalk: Webhook POST
    - GitHub Pages: Commit & push docs/
```

## Components

### 1. Data Collection (`scripts/collect_data.sh`)

**Input:** DATE (YYYY-MM-DD), defaults to yesterday

**gh CLI Commands:**
```bash
# New issues (created since DATE)
gh issue list --repo apache/fluss --state all --limit 50 \
  --search "created:>=$DATE" --json number,title,state,labels,url,createdAt,author

# Closed issues
gh issue list --repo apache/fluss --state closed --limit 30 \
  --search "closed:>=$DATE" --json number,title,closedAt,author,url

# Open PRs
gh pr list --repo apache/fluss --state open --limit 50 \
  --search "created:>=$DATE" --json number,title,labels,url,createdAt,author

# Merged PRs
gh pr list --repo apache/fluss --state merged --limit 30 \
  --search "merged:>=$DATE" --json number,title,mergedAt,author,url,labels

# Issue comments
gh api "repos/apache/fluss/issues/comments?since=$DATE" \
  --jq '.[] | {issue_number: .issue_url, body, user: .user.login, created_at}'

# PR review comments
gh api "repos/apache/fluss/pulls/comments?since=$DATE" \
  --jq '.[] | {pr_number: .pull_request_url, body, user: .user.login, path, created_at}'
```

**Output:** `raw_data.json`
```json
{
  "date": "2026-03-11",
  "repo": "apache/fluss",
  "new_issues": [...],
  "closed_issues": [...],
  "open_prs": [...],
  "merged_prs": [...],
  "issue_comments": [...],
  "pr_review_comments": [...]
}
```

### 2. Claude API Integration

**Action:** `anthropic/claude-code-action@v1`

**Environment Variables (from GitHub Secrets):**
- `ANTHROPIC_BASE_URL` - Custom API endpoint
- `ANTHROPIC_AUTH_TOKEN` - Auth token

**Prompt (`prompts/summarize.md`):**
- Input: raw_data.json content
- Generate: 核心要点 (3-5 highlights), 重点关注 (critical bugs), Issue/PR 动态摘要

**Output:** `summary.json`
```json
{
  "highlights": [
    "🎉 PR #123 合并: 实现了新的 TableScan 优化",
    "🐛 修复了 #456 中的内存泄漏问题"
  ],
  "critical_issues": [
    "⚠️ Issue #789: 生产环境数据丢失问题"
  ],
  "issue_comments_summary": "主要讨论集中在...",
  "pr_review_summary": "代码审查重点关注..."
}
```

### 3. Report Generation (`scripts/generate_report.py`)

**Inputs:**
- `raw_data.json`
- `summary.json`

**Output 1: Full HTML Report**

Structure:
1. 🔥 核心要点 (from Claude)
2. ⚠️ 重点关注 (重大 bug, critical issues)
3. 📝 新建 Issue/PR
   - 新建 Issues 列表
   - 新建 PRs 列表
4. 💬 Issue/PR 动态
   - Issue Comments 总结
   - PR Review Comments 总结
5. ✅ 关闭 Issue/PR
   - 已关闭 Issues
   - 已合并 PRs

**Output 2: DingTalk Message**

```markdown
## 🌊 Fluss 每日动态 (2026-03-11)

📊 **统计**: 3 新 Issues | 2 关闭 | 5 新 PR | 4 合并

🔥 **核心要点**:
- PR #123 合并: TableScan 优化
- Issue #456 修复: 内存泄漏

⚠️ **需要关注**: 
- Issue #789: 数据丢失问题

🔗 [查看完整报告](https://user.github.io/daily-reports/reports/2026-03-11.html)
```

### 4. GitHub Pages Archive

**Structure:**
```
docs/
├── index.html          # 归档首页 (auto-generated)
├── reports/
│   ├── 2026-03-12.html
│   ├── 2026-03-11.html
│   └── ...
└── assets/
    └── style.css
```

**index.html:** Single-page infinite scroll
- 按月/周分组
- 可展开/折叠
- 点击展开显示当天报告详情

### 5. GitHub Actions Workflow

**File:** `.github/workflows/daily-report.yml`

```yaml
name: Daily Report

on:
  schedule:
    - cron: '0 1 * * *'  # UTC 01:00 = Beijing 09:00
  workflow_dispatch:
    inputs:
      date:
        description: '报告日期 (YYYY-MM-DD)'
        required: false
        default: ''

jobs:
  generate-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Collect GitHub data
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: bash scripts/collect_data.sh ${{ inputs.date }}
      
      - name: Generate summary (Claude)
        uses: anthropic/claude-code-action@v1
        env:
          ANTHROPIC_BASE_URL: ${{ secrets.ANTHROPIC_BASE_URL }}
          ANTHROPIC_AUTH_TOKEN: ${{ secrets.ANTHROPIC_AUTH_TOKEN }}
        with:
          prompt_file: prompts/summarize.md
      
      - name: Generate reports
        run: python scripts/generate_report.py
      
      - name: Send to DingTalk
        run: |
          curl -X POST "${{ secrets.DINGTALK_WEBHOOK }}" \
            -H "Content-Type: application/json" \
            -d @dingtalk_message.json
      
      - name: Commit HTML to Pages
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add docs/
          git commit -m "chore: add daily report"
          git push
```

## Required Secrets

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_BASE_URL` | Custom Claude API endpoint |
| `ANTHROPIC_AUTH_TOKEN` | Claude API auth token |
| `DINGTALK_WEBHOOK` | DingTalk robot webhook URL |

## File Structure

```
daily-reports/
├── .github/
│   └── workflows/
│       └── daily-report.yml
├── scripts/
│   ├── collect_data.sh
│   └── generate_report.py
├── prompts/
│   └── summarize.md
├── docs/
│   ├── index.html
│   ├── reports/
│   └── assets/
│       └── style.css
└── README.md
```

## Manual Trigger

Run for specific date:
```
gh workflow run daily-report.yml -f date=2026-03-10
```

Or via GitHub UI: Actions → Daily Report → Run workflow → Input date
