#!/usr/bin/env python3
"""Generate summary using an OpenAI-compatible API."""

import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

MAX_RETRIES = int(os.environ.get("OPENAI_MAX_RETRIES", "2"))
RETRY_DELAY_SECONDS = int(os.environ.get("OPENAI_RETRY_DELAY", "5"))
TIMEOUT_SECONDS = int(os.environ.get("OPENAI_TIMEOUT", "180"))


def load_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def extract_number(url: str) -> int | None:
    match = re.search(r'(\d+)$', url or '')
    return int(match.group(1)) if match else None


def summarize_text(text: str, limit: int = 100) -> str:
    cleaned = ' '.join((text or '').split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit - 1].rstrip() + '…'


def normalize_summary(summary: dict) -> dict:
    return {
        "highlights": summary.get("highlights") or ["暂无重要更新"],
        "critical_issues": summary.get("critical_issues") or [],
        "issue_activity": summary.get("issue_activity") or [],
        "pr_activity": summary.get("pr_activity") or [],
    }


def build_fallback_highlights(raw_data: dict) -> list[str]:
    highlights = []
    seen = set()
    sources = [
        ("merged_prs", "🎉", "PR"),
        ("new_issues", "🐛", "Issue"),
        ("open_prs", "✨", "PR"),
        ("closed_issues", "✅", "Issue"),
    ]
    for source, emoji, item_type in sources:
        for item in raw_data.get(source, []):
            number = item.get("number")
            url = item.get("url")
            title = item.get("title", "").strip()
            key = (item_type, number)
            if not number or not url or not title or key in seen:
                continue
            highlights.append(f"{emoji} [{item_type} #{number}]({url}) {title}")
            seen.add(key)
            if len(highlights) >= 5:
                return highlights
    return highlights or ["暂无重要更新"]


def build_critical_issues(raw_data: dict) -> list[str]:
    critical_issues = []
    for issue in raw_data.get("new_issues", []) + raw_data.get("closed_issues", []) + raw_data.get("commented_issues", []):
        labels = issue.get("labels", [])
        label_names = {
            label.get("name", "").lower()
            for label in labels
            if isinstance(label, dict)
        }
        if not any(any(keyword in label for keyword in ("bug", "critical", "p0", "p1", "high-priority")) for label in label_names):
            continue
        number = issue.get("number")
        url = issue.get("url")
        title = issue.get("title", "").strip()
        if number and url and title:
            critical_issues.append(f"⚠️ [Issue #{number}]({url}) {title}")
    return critical_issues


def build_activity(raw_data: dict, item_key: str, comment_key: str, url_field: str) -> list[dict]:
    items = {
        item.get("number"): item
        for item in raw_data.get(item_key, [])
        if item.get("number")
    }
    grouped = {}
    for comment in raw_data.get(comment_key, []):
        number = extract_number(comment.get(url_field, ""))
        if number not in items:
            continue
        user = comment.get("user") or "unknown"
        summary = summarize_text(comment.get("body", ""))
        if not summary:
            continue
        grouped.setdefault(number, {}).setdefault(user, []).append(summary)

    activity = []
    for number, comments_by_user in grouped.items():
        item = items[number]
        comments = [
            {"user": user, "summary": summarize_text("；".join(dict.fromkeys(summaries)))}
            for user, summaries in comments_by_user.items()
        ]
        if comments:
            activity.append({
                "number": number,
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "comments": comments,
            })
    return activity


def build_fallback_summary(raw_data: dict) -> dict:
    return {
        "highlights": build_fallback_highlights(raw_data),
        "critical_issues": build_critical_issues(raw_data),
        "issue_activity": build_activity(raw_data, "commented_issues", "issue_comments", "issue_url"),
        "pr_activity": build_activity(raw_data, "commented_prs", "pr_review_comments", "pull_request_url"),
    }


def call_llm_api(base_url: str, api_key: str, model: str, prompt: str) -> str:
    """Call LLM API (OpenAI-compatible format)."""
    # If base_url ends with version path, use /chat/completions directly
    # Otherwise use /v1/chat/completions
    if base_url.rstrip('/').endswith(('/v1', '/v2', '/v3', '/v4')):
        url = f"{base_url.rstrip('/')}/chat/completions"
    else:
        url = f"{base_url.rstrip('/')}/v1/chat/completions"
    
    data = json.dumps({
        "model": model,
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }).encode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers)

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                return result["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8', errors='replace')
            last_error = f"API Error (attempt {attempt}/{MAX_RETRIES}): {e.code} - {error_body}"
            print(last_error)
            if 400 <= e.code < 500 and e.code not in (408, 429):
                break
        except (TimeoutError, urllib.error.URLError, OSError) as e:
            last_error = f"LLM API error (attempt {attempt}/{MAX_RETRIES}): {e}"
            print(last_error)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS * attempt)

    raise RuntimeError(last_error or "LLM API call failed")


def parse_summary_response(response: str) -> dict:
    try:
        return normalize_summary(json.loads(response))
    except json.JSONDecodeError:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if match:
            return normalize_summary(json.loads(match.group(1)))
        raise ValueError(f"Failed to parse response: {response[:500]}")


def main():
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com")
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL", "glm-5")
    
    if not api_key:
        print("Error: OPENAI_API_KEY required")
        sys.exit(1)
    
    # Load raw data and prompt template
    raw_data = load_file("raw_data.json")
    prompt_template = load_file("prompts/fluss-github-summarize.md")
    
    # Build prompt
    prompt = prompt_template.replace("{{RAW_DATA}}", raw_data)
    
    print(f"Calling {model} at {base_url}...")
    try:
        response = call_llm_api(base_url, api_key, model, prompt)
        summary = parse_summary_response(response)
    except (RuntimeError, ValueError) as e:
        print(f"LLM summary failed: {e}")
        print("Falling back to deterministic summary...")
        summary = build_fallback_summary(json.loads(raw_data))
    
    # Save summary
    with open("summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("Summary saved to summary.json")


if __name__ == "__main__":
    main()
