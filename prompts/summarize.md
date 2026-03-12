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
  "issue_comments_summary": "Issue 讨论的主要内容摘要...",
  "pr_review_summary": "PR Review 的主要关注点摘要..."
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

3. **issue_comments_summary**: 50-100字摘要
   - 总结主要讨论话题
   - 如果没有评论则返回 "今日无新评论"

4. **pr_review_summary**: 50-100字摘要
   - 总结 code review 的主要关注点
   - 如果没有评论则返回 "今日无新 Review 评论"

Only output valid JSON, no other text.
