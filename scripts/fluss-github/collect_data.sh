#!/bin/bash
set -e

# Input: DATE (YYYY-MM-DD), defaults to yesterday
# macOS uses -v, Linux uses -d
DATE=${1:-$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)}
REPO="apache/fluss"
OUTPUT_FILE="raw_data.json"

echo "Collecting data for $REPO since $DATE..."

# New issues (created since DATE)
echo "Fetching new issues..."
NEW_ISSUES=$(gh issue list --repo $REPO --state all --limit 50 \
  --search "created:>=$DATE" \
  --json number,title,state,labels,url,createdAt,author 2>/dev/null || echo "[]")

# Closed issues
echo "Fetching closed issues..."
CLOSED_ISSUES=$(gh issue list --repo $REPO --state closed --limit 30 \
  --search "closed:>=$DATE" \
  --json number,title,closedAt,author,url,labels 2>/dev/null || echo "[]")

# Open PRs (created since DATE)
echo "Fetching open PRs..."
OPEN_PRS=$(gh pr list --repo $REPO --state open --limit 50 \
  --search "created:>=$DATE" \
  --json number,title,labels,url,createdAt,author 2>/dev/null || echo "[]")

# Merged PRs
echo "Fetching merged PRs..."
MERGED_PRS=$(gh pr list --repo $REPO --state merged --limit 30 \
  --search "merged:>=$DATE" \
  --json number,title,mergedAt,author,url,labels 2>/dev/null || echo "[]")

# Issue comments
echo "Fetching issue comments..."
ISSUE_COMMENTS=$(gh api "repos/$REPO/issues/comments?since=${DATE}T00:00:00Z&per_page=100" \
  --jq '[.[] | {issue_url, body, user: .user.login, created_at}]' 2>/dev/null || echo "[]")

# PR review comments
echo "Fetching PR review comments..."
PR_COMMENTS=$(gh api "repos/$REPO/pulls/comments?since=${DATE}T00:00:00Z&per_page=100" \
  --jq '[.[] | {pull_request_url, body, user: .user.login, path, created_at}]' 2>/dev/null || echo "[]")

# Extract issue numbers from comments and fetch their titles
echo "Fetching titles for commented issues..."
COMMENTED_ISSUE_NUMBERS=$(echo "$ISSUE_COMMENTS" | jq -r '.[].issue_url' | grep -oE '[0-9]+$' | sort -u)
COMMENTED_ISSUES="[]"
for num in $COMMENTED_ISSUE_NUMBERS; do
  ISSUE_INFO=$(gh api "repos/$REPO/issues/$num" --jq '{number, title, url: .html_url}' 2>/dev/null || echo "")
  if [ -n "$ISSUE_INFO" ]; then
    COMMENTED_ISSUES=$(echo "$COMMENTED_ISSUES" | jq ". + [$ISSUE_INFO]")
  fi
done

# Extract PR numbers from review comments and fetch their titles
echo "Fetching titles for commented PRs..."
COMMENTED_PR_NUMBERS=$(echo "$PR_COMMENTS" | jq -r '.[].pull_request_url' | grep -oE '[0-9]+$' | sort -u)
COMMENTED_PRS="[]"
for num in $COMMENTED_PR_NUMBERS; do
  PR_INFO=$(gh api "repos/$REPO/pulls/$num" --jq '{number, title, url: .html_url}' 2>/dev/null || echo "")
  if [ -n "$PR_INFO" ]; then
    COMMENTED_PRS=$(echo "$COMMENTED_PRS" | jq ". + [$PR_INFO]")
  fi
done

# Assemble JSON output
cat > $OUTPUT_FILE << EOF
{
  "date": "$DATE",
  "repo": "$REPO",
  "new_issues": $NEW_ISSUES,
  "closed_issues": $CLOSED_ISSUES,
  "open_prs": $OPEN_PRS,
  "merged_prs": $MERGED_PRS,
  "issue_comments": $ISSUE_COMMENTS,
  "pr_review_comments": $PR_COMMENTS,
  "commented_issues": $COMMENTED_ISSUES,
  "commented_prs": $COMMENTED_PRS
}
EOF

echo "Data saved to $OUTPUT_FILE"
echo "Summary:"
echo "  - New issues: $(echo "$NEW_ISSUES" | jq 'length')"
echo "  - Closed issues: $(echo "$CLOSED_ISSUES" | jq 'length')"
echo "  - Open PRs: $(echo "$OPEN_PRS" | jq 'length')"
echo "  - Merged PRs: $(echo "$MERGED_PRS" | jq 'length')"
