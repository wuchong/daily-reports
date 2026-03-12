# 🌊 Fluss Daily Reports

Apache Fluss 仓库每日动态报告系统，自动汇总 GitHub 活动，输出精简钉钉消息和完整 HTML 归档。

## 功能

- **每日自动运行**：北京时间每天 9:00 自动执行
- **手动补跑**：支持手动指定日期生成历史报告
- **双输出**：
  - 📱 钉钉机器人：精简摘要（统计 + 核心要点 + 重点关注）
  - 🌐 GitHub Pages：完整 HTML 报告归档

## 报告内容

| 章节 | 说明 |
|------|------|
| 🔥 核心要点 | 3-5 条重要更新（Claude 智能生成） |
| ⚠️ 重点关注 | 重大 bug、critical issues |
| 📝 新建 Issue/PR | 当日新建的 Issues 和 PRs |
| 💬 Issue/PR 动态 | Issue 讨论和 PR Review 摘要 |
| ✅ 关闭 Issue/PR | 已关闭 Issues 和已合并 PRs |

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
| `ANTHROPIC_BASE_URL` | Claude API 地址 |
| `ANTHROPIC_AUTH_TOKEN` | Claude API Token |
| `DINGTALK_WEBHOOK` | 钉钉机器人 Webhook URL |

### 3. 启用 GitHub Pages

Settings → Pages → Source: Deploy from branch → `main` branch, `/docs` folder

### 4. 测试运行

```bash
# 手动触发（指定日期）
gh workflow run daily-report.yml -f date=2026-03-11

# 或通过 GitHub UI
# Actions → Daily Report → Run workflow
```

## 项目结构

```
daily-reports/
├── .github/workflows/
│   └── daily-report.yml     # GitHub Actions 工作流
├── scripts/
│   ├── collect_data.sh      # 数据采集（gh CLI）
│   └── generate_report.py   # 报告生成
├── prompts/
│   └── summarize.md         # Claude 提示词
├── docs/
│   ├── index.html           # 归档首页
│   ├── assets/style.css     # 样式
│   └── reports/             # 每日报告
└── README.md
```

## 工作流程

```
┌─────────────────────────────────────────┐
│  GitHub Actions (每天 9:00 北京时间)     │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  1. 数据采集 (gh CLI)                    │
│     - Issues/PRs 动态                    │
│     - Comments 和 Reviews               │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  2. Claude API 智能摘要                  │
│     - 核心要点提取                       │
│     - 重点问题识别                       │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  3. 报告生成                             │
│     - HTML 完整报告                      │
│     - 钉钉 Markdown 消息                 │
└─────────────────┬───────────────────────┘
                  │
          ┌───────┴───────┐
          ▼               ▼
    ┌──────────┐    ┌──────────┐
    │ 钉钉推送  │    │ Pages 发布│
    └──────────┘    └──────────┘
```

## 本地开发

```bash
# 采集数据
export GH_TOKEN=$(gh auth token)
bash scripts/collect_data.sh 2026-03-11

# 生成报告（需要先创建 summary.json）
python3 scripts/generate_report.py

# 预览
open docs/reports/2026-03-11.html
```

## License

MIT
