#!/usr/bin/env python3
"""Send daily report to DingTalk."""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse

import requests


GITHUB_PAGES_URL = os.environ.get('GITHUB_PAGES_URL', 'https://example.github.io/daily-reports')


def load_summary():
    """Load summary data."""
    with open('summary.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_sign(secret: str) -> tuple:
    """Generate DingTalk signature."""
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode('utf-8')
    string_to_sign = f'{timestamp}\n{secret}'
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def build_message(summary: dict) -> dict:
    """Build DingTalk markdown message."""
    date = summary.get('date', '')
    
    # Build top 3 changes
    top_changes = ''
    for i, change in enumerate(summary.get('top_3_changes', []), 1):
        top_changes += f'{i}. **{change.get("title", "")}** — {change.get("summary", "")}\n'
    
    report_url = f'{GITHUB_PAGES_URL}/data-ai/reports/{date}.html'
    
    markdown_content = f'''## Data+AI 全球日报 ({date})

🔥 **今日最重要的3个变化**

{top_changes}
**总判断**：{summary.get("overall_judgment", "")}

🔗 [查看完整报告]({report_url})'''

    return {
        "msgtype": "markdown",
        "markdown": {
            "title": f"Data+AI 全球日报 ({date})",
            "text": markdown_content
        }
    }


def send_dingtalk(webhook: str, secret: str, message: dict) -> bool:
    """Send message to DingTalk."""
    timestamp, sign = generate_sign(secret)
    url = f'{webhook}&timestamp={timestamp}&sign={sign}'
    
    headers = {'Content-Type': 'application/json'}
    
    try:
        resp = requests.post(url, json=message, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        
        if result.get('errcode') == 0:
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
    webhook = os.environ.get('DINGTALK_WEBHOOK')
    secret = os.environ.get('DINGTALK_SECRET')
    
    if not webhook or not secret:
        print("Warning: DINGTALK_WEBHOOK or DINGTALK_SECRET not set")
        sys.exit(1)
    
    summary = load_summary()
    message = build_message(summary)
    
    # Save message for debugging
    with open('dingtalk_message.json', 'w', encoding='utf-8') as f:
        json.dump(message, f, ensure_ascii=False, indent=2)
    print("Message saved to dingtalk_message.json")
    
    # Send to DingTalk
    success = send_dingtalk(webhook, secret, message)
    if not success:
        sys.exit(1)


if __name__ == '__main__':
    main()
