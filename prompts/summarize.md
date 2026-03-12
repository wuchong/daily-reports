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
    "🎉 [PR #123](https://github.com/apache/fluss/pull/123) 描述重要的 PR 合并或功能",
    "🐛 [Issue #456](https://github.com/apache/fluss/issues/456) 描述重要的 bug 修复",
    "✨ 描述其他亮点"
  ],
  "critical_issues": [
    "⚠️ [Issue #789](https://github.com/apache/fluss/issues/789) 描述需要紧急关注的问题"
  ],
  "issue_activity": [
    {
      "number": 123,
      "title": "Issue 标题",
      "url": "https://github.com/apache/fluss/issues/123",
      "points": [
        "讨论要点1: xxx",
        "讨论要点2: xxx"
      ]
    }
  ],
  "pr_activity": [
    {
      "number": 456,
      "title": "PR 标题",
      "url": "https://github.com/apache/fluss/pull/456",
      "points": [
        "Review 要点1: xxx",
        "Review 要点2: xxx"
      ]
    }
  ]
}
```

## Guidelines

1. **highlights**: 3-5 条核心要点
   - 优先展示已合并的重要 PR
   - 包含重要 bug 修复
   - 使用 emoji: 🎉(合并) 🐛(bug) ✨(新功能) 🚀(性能) 📚(文档)
   - **必须包含完整链接**: 使用 `[PR #编号](url)` 或 `[Issue #编号](url)` 格式

2. **critical_issues**: 需要关注的问题
   - 查找包含 bug, critical, P0, P1, high-priority 标签的 issue
   - **必须包含完整链接**: 使用 `[Issue #编号](url)` 格式
   - 如果没有则返回空数组

3. **issue_activity**: 按 Issue 组织的讨论要点
   - 每个 Issue 包含 number, title, url, points
   - points 是讨论的主要要点列表（每条 20-50 字）
   - 如果没有评论则返回空数组

4. **pr_activity**: 按 PR 组织的 Review 要点
   - 每个 PR 包含 number, title, url, points
   - points 是 Review 的主要要点列表（每条 20-50 字）
   - 如果没有评论则返回空数组

Only output valid JSON, no other text.
