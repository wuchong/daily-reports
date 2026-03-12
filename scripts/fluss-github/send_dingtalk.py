#!/usr/bin/env python3
"""Send message to DingTalk with signature verification."""

import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.request
import urllib.error
import urllib.parse


def generate_sign(timestamp: int, secret: str) -> str:
    """Generate DingTalk signature."""
    string_to_sign = f"{timestamp}\n{secret}"
    hmac_code = hmac.new(
        secret.encode('utf-8'),
        string_to_sign.encode('utf-8'),
        digestmod=hashlib.sha256
    ).digest()
    return urllib.parse.quote_plus(base64.b64encode(hmac_code).decode('utf-8'))


def send_dingtalk(webhook: str, secret: str, message: dict) -> bool:
    """Send message to DingTalk webhook."""
    timestamp = int(time.time() * 1000)
    sign = generate_sign(timestamp, secret)
    
    url = f"{webhook}&timestamp={timestamp}&sign={sign}"
    
    data = json.dumps(message).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            if result.get("errcode") == 0:
                print("DingTalk message sent successfully")
                return True
            else:
                print(f"DingTalk error: {result}")
                return False
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.read().decode('utf-8')}")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def main():
    webhook = os.environ.get("DINGTALK_WEBHOOK")
    secret = os.environ.get("DINGTALK_SECRET")
    
    if not webhook:
        print("Error: DINGTALK_WEBHOOK required")
        sys.exit(1)
    
    if not secret:
        print("Error: DINGTALK_SECRET required for signature verification")
        sys.exit(1)
    
    # Load message
    with open("dingtalk_message.json", "r", encoding="utf-8") as f:
        message = json.load(f)
    
    success = send_dingtalk(webhook, secret, message)
    
    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
