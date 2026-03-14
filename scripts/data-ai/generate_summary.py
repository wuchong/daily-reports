#!/usr/bin/env python3
"""Generate summary using LLM from collected news."""

import json
import os
from pathlib import Path

from openai import OpenAI


def load_prompt():
    """Load the summarization prompt."""
    prompt_path = Path(__file__).parent.parent.parent / 'prompts' / 'data-ai-summarize.md'
    with open(prompt_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_raw_news():
    """Load collected news data."""
    if not os.path.exists('raw_news.json'):
        print("Warning: raw_news.json not found, creating empty data")
        return {'date': '', 'items': []}
    with open('raw_news.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_summary(client: OpenAI, prompt: str, news_data: dict) -> dict:
    """Call LLM to generate summary."""
    user_content = f"""以下是今日采集的新闻数据：

```json
{json.dumps(news_data, ensure_ascii=False, indent=2)}
```

请根据 prompt 要求生成 Data+AI 全球日报。只输出 JSON，不要有其他内容。"""

    try:
        response = client.chat.completions.create(
            model="glm-5",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content}
            ],
            max_tokens=8000,
            temperature=0.3
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from response
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        elif '```' in content:
            content = content.split('```')[1].split('```')[0]
        
        return json.loads(content.strip())
    except Exception as e:
        print(f"Error calling LLM API: {e}")
        raise


def main():
    """Main entry point."""
    # Initialize client
    base_url = os.environ.get('OPENAI_BASE_URL')
    api_key = os.environ.get('OPENAI_API_KEY')
    
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required")
    
    client = OpenAI(base_url=base_url, api_key=api_key)
    
    # Load data
    prompt = load_prompt()
    news_data = load_raw_news()
    
    items_count = len(news_data.get('items', []))
    print(f"Generating summary for {items_count} items...")
    
    # If no items, create empty summary
    if items_count == 0:
        print("Warning: No news items found, creating empty summary")
        summary = {
            'date': news_data.get('date', ''),
            'sections': [],
            'total_items': 0
        }
    else:
        # Generate summary
        summary = generate_summary(client, prompt, news_data)
    
    # Save output
    with open('summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("Summary saved to summary.json")


if __name__ == '__main__':
    main()
