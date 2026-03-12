#!/usr/bin/env python3
"""Generate summary using Claude API."""

import json
import os
import sys
import urllib.request
import urllib.error


def load_file(path: str) -> str:
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def call_claude_api(base_url: str, api_key: str, prompt: str) -> str:
    """Call Claude API and return response."""
    url = f"{base_url.rstrip('/')}/v1/messages"
    
    data = json.dumps({
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 4096,
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }).encode('utf-8')
    
    headers = {
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers)
    
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        print(f"API Error: {e.code} - {e.read().decode('utf-8')}")
        sys.exit(1)


def main():
    base_url = os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("Error: ANTHROPIC_API_KEY required")
        sys.exit(1)
    
    # Load raw data and prompt template
    raw_data = load_file("raw_data.json")
    prompt_template = load_file("prompts/summarize.md")
    
    # Build prompt
    prompt = prompt_template.replace("{{RAW_DATA}}", raw_data)
    
    print(f"Calling Claude API at {base_url}...")
    response = call_claude_api(base_url, api_key, prompt)
    
    # Extract JSON from response
    try:
        # Try to parse directly
        summary = json.loads(response)
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', response)
        if match:
            summary = json.loads(match.group(1))
        else:
            print(f"Failed to parse response: {response[:500]}")
            sys.exit(1)
    
    # Save summary
    with open("summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("Summary saved to summary.json")


if __name__ == "__main__":
    main()
