# 🌊 Daily Reports

自动化报告系统，聚合多个数据源生成每日/每周报告，支持钉钉推送和 GitHub Pages 归档。

## 报告类型

### 📅 日报

| 报告 | 数据源 | 运行时间 | 说明 |
|------|--------|----------|------|
| Fluss GitHub Daily | GitHub API | 每天 07:00 | Apache Fluss 仓库动态 |
| Data+AI Daily | 多源聚合 | 每天 07:00 | AI/大数据行业新闻、论文、开源动态 |

### 📊 周报（社区邮件列表）

| 报告 | 邮件列表 | 运行时间 |
|------|----------|----------|
| Spark Dev Weekly | dev@spark.apache.org | 周一 07:00 |
| Iceberg Dev Weekly | dev@iceberg.apache.org | 周二 07:00 |
| Kafka Dev Weekly | dev@kafka.apache.org | 周三 07:00 |
| Flink Dev Weekly | dev@flink.apache.org | 周四 07:00 |
| Fluss Dev Weekly | dev@fluss.apache.org | 周五 07:00 |

## 功能特性

- **自动调度**：GitHub Actions 定时执行
- **手动补跑**：支持指定日期/周数生成历史报告
- **LLM 智能摘要**：自动提取核心要点
- **双输出**：
  - 📱 钉钉机器人推送
  - 🌐 GitHub Pages 归档

## 快速开始

### 1. Fork 或 Clone 本仓库

```bash
git clone https://github.com/YOUR_USERNAME/daily-reports.git
cd daily-reports
```

### 2. 配置 GitHub Secrets

在仓库 Settings → Secrets and variables → Actions 中添加：

| Secret | 说明 |
|--------|------|
| `OPENAI_BASE_URL` | LLM API 地址（OpenAI 兼容） |
| `OPENAI_API_KEY` | LLM API Key |
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook URL |
| `DINGTALK_SECRET` | 钉钉机器人加签密钥 |

### 3. 启用 GitHub Pages

Settings → Pages → Source: Deploy from branch → `pages` branch, `/ (root)` folder

### 4. 测试运行

```bash
# 手动触发日报
gh workflow run fluss-github-daily-report.yml -f date=2026-03-11
gh workflow run data-ai-daily-report.yml -f date=2026-03-11

# 手动触发周报
gh workflow run flink-dev-weekly-report.yml -f week=2026-W10
```

## 项目结构

```
daily-reports/
├── .github/workflows/
│   ├── fluss-github-daily-report.yml    # Fluss GitHub 日报
│   ├── data-ai-daily-report.yml         # Data+AI 日报
│   ├── flink-dev-weekly-report.yml      # Flink 邮件列表周报
│   ├── fluss-dev-weekly-report.yml      # Fluss 邮件列表周报
│   ├── spark-dev-weekly-report.yml      # Spark 邮件列表周报
│   ├── kafka-dev-weekly-report.yml      # Kafka 邮件列表周报
│   └── iceberg-dev-weekly-report.yml    # Iceberg 邮件列表周报
├── scripts/
│   ├── fluss-github/                    # Fluss GitHub 日报脚本
│   │   ├── collect_data.sh
│   │   ├── generate_summary.py
│   │   ├── generate_report.py
│   │   └── send_dingtalk.py
│   ├── data-ai/                         # Data+AI 日报脚本
│   │   ├── search_news.py
│   │   ├── generate_summary.py
│   │   ├── generate_report.py
│   │   └── send_dingtalk.py
│   └── mailing-list/                    # 邮件列表周报脚本（通用）
│       ├── fetch_emails.py
│       ├── classify_emails.py
│       ├── generate_summary.py
│       ├── generate_report.py
│       └── send_dingtalk.py
├── prompts/
│   ├── fluss-github-summarize.md        # Fluss GitHub 提示词
│   ├── data-ai-summarize.md             # Data+AI 提示词
│   └── mailing-list-summarize.md        # 邮件列表提示词
├── assets/                              # 静态资源
│   ├── index.html                       # 归档首页模板
│   ├── fluss-github/style.css
│   ├── data-ai/style.css
│   └── mailing-list/style.css
└── README.md
```

## 报告内容

### Fluss GitHub Daily

| 章节 | 说明 |
|------|------|
| 🔥 核心要点 | 3-5 条重要更新（LLM 智能生成） |
| ⚠️ 重点关注 | 重大 bug、critical issues |
| 📝 新建 Issue/PR | 当日新建的 Issues 和 PRs |
| 💬 Issue/PR 动态 | Issue 讨论和 PR Review 摘要 |
| ✅ 关闭 Issue/PR | 已关闭 Issues 和已合并 PRs |

### Data+AI Daily

| 章节 | 说明 |
|------|------|
| 📰 行业新闻 | AI/大数据领域重要新闻 |
| 📄 论文精选 | arXiv 等最新研究论文 |
| 🔧 开源动态 | GitHub 热门项目更新 |
| 📈 股票分析 | 相关科技公司股价动态 |

### 社区邮件列表周报

| 章节 | 说明 |
|------|------|
| 📢 公告 | Release、版本发布相关 |
| 🗳️ 投票 | VOTE 投票及结果 |
| 💬 讨论 | DISCUSS 技术讨论摘要 |
| 🎫 JIRA | Bug 修复、新功能、改进等 |

## License

MIT
