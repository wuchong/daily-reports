#!/usr/bin/env python3
"""Send weekly report to DingTalk.

Environment variables:
- PROJECT_NAME: Project display name (e.g., Flink, Iceberg, Kafka, Spark)
- PROJECT_ID: Project identifier for paths (e.g., flink-dev, iceberg-dev)
- DINGTALK_WEBHOOK: DingTalk webhook URL
- DINGTALK_SECRET: DingTalk signing secret
- GITHUB_PAGES_URL: Base URL for GitHub Pages
"""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse

import requests


GITHUB_PAGES_URL = os.environ.get("GITHUB_PAGES_URL", "https://example.github.io/daily-reports")
MAX_DISCUSSIONS = 5  # Limit discussions in DingTalk message


def load_summary() -> dict:
    """Load summary data."""
    with open("summary.json", "r", encoding="utf-8") as f:
        return json.load(f)


def generate_sign(secret: str) -> tuple[str, str]:
    """Generate DingTalk signature."""
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode("utf-8")
    string_to_sign = f"{timestamp}\n{secret}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def build_message(summary: dict, project_name: str, project_id: str) -> dict:
    """Build DingTalk markdown message."""
    week = summary.get("week", "")
    date_range = summary.get("date_range", {})
    start = date_range.get("start", "")
    end = date_range.get("end", "")
    
    # Announcements
    announcements = summary.get("announcements", [])
    announce_text = ""
    if announcements:
        announce_text = f"📢 **公告** ({len(announcements)})\n"
        for a in announcements:
            announce_text += f"- {a['subject']} [🔗]({a['link']})\n"
    else:
        announce_text = "📢 **公告** (0)\n- 本周无公告\n"
    
    # Votes
    votes = summary.get("votes", [])
    vote_text = ""
    if votes:
        vote_text = f"🗳️ **投票** ({len(votes)})\n"
        for v in votes:
            status = "⚠️ 有异议" if v.get("has_objection") else "✅ 已通过"
            vote_text += f"- {v['subject']} → {status} [🔗]({v['link']})\n"
            if v.get("has_objection") and v.get("objection_summary"):
                vote_text += f"  {v['objection_summary']}\n"
    else:
        vote_text = "🗳️ **投票** (0)\n- 本周无投票\n"
    
    # Discussions (top N)
    discussions = summary.get("discussions", [])[:MAX_DISCUSSIONS]
    discuss_text = ""
    if discussions:
        discuss_text = f"💬 **讨论** ({len(summary.get('discussions', []))})\n\n"
        for i, d in enumerate(discussions, 1):
            llm_summary = d.get("llm_summary", {})
            summary_text = llm_summary.get("summary", "")
            
            discuss_text += f"**{i}. [{d['subject']}]({d['link']})**\n\n"
            discuss_text += f"{summary_text}\n\n"
    else:
        discuss_text = "💬 **讨论** (0)\n- 本周无讨论\n"
    
    # JIRA
    jira_count = summary.get("jira_count", 0)
    jira_summary = summary.get("jira_summary", "")
    jira_text = f"🎫 **JIRA**: 本周新建 {jira_count} 个\n{jira_summary}\n"
    
    # Report link
    report_url = f"{GITHUB_PAGES_URL}/{project_id}/reports/{week}.html"
    
    markdown_content = f"""## {project_name} 社区周报 ({start} ~ {end})

{announce_text}
{vote_text}
{discuss_text}
{jira_text}
🔗 [查看完整报告]({report_url})"""

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"{project_name} 社区周报 ({week})",
            "text": markdown_content
        }
    }


def send_dingtalk(webhook: str, secret: str, message: dict) -> bool:
    """Send message to DingTalk."""
    timestamp, sign = generate_sign(secret)
    url = f"{webhook}&timestamp={timestamp}&sign={sign}"
    
    headers = {"Content-Type": "application/json"}
    
    try:
        resp = requests.post(url, json=message, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get("errcode") == 0:
            print("DingTalk message sent successfully")
            return True
        else:
            print(f"DingTalk error: {result}")
            return False
    except Exception as e:
        print(f"DingTalk request failed: {e}")
        return False


def main():
    """Main entry point."""
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    secret = os.environ.get("DINGTALK_SECRET")
    project_name = os.environ.get("PROJECT_NAME", "Apache")
    project_id = os.environ.get("PROJECT_ID", "mailing-list")
    
    if not webhook or not secret:
        print("Error: DINGTALK_WEBHOOK or DINGTALK_SECRET not set")
        sys.exit(1)
    
    summary = load_summary()
    message = build_message(summary, project_name, project_id)
    
    # Save message for debugging
    with open("dingtalk_message.json", "w", encoding="utf-8") as f:
        json.dump(message, f, ensure_ascii=False, indent=2)
    print("Message saved to dingtalk_message.json")
    
    # Send to DingTalk
    success = send_dingtalk(webhook, secret, message)
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
