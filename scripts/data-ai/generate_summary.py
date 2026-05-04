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


def compress_news_data(news_data: dict, max_items: int = 100, max_snippet_len: int = 300) -> dict:
    """Compress news data to fit within LLM token limits.
    
    - Remove full content field (too large)
    - Truncate snippets
    - Limit number of items
    """
    items = news_data.get('items', [])
    
    compressed_items = []
    for item in items[:max_items]:
        compressed_item = {
            'title': item.get('title', ''),
            'url': item.get('url', ''),
            'snippet': (item.get('snippet', '') or '')[:max_snippet_len],
            'source': item.get('source', ''),
            'published': item.get('published', '')
        }
        compressed_items.append(compressed_item)
    
    return {
        'date': news_data.get('date', ''),
        'items': compressed_items,
        'total_collected': len(items),
        'included_in_summary': len(compressed_items)
    }


def try_parse_json(content: str) -> dict | None:
    """Try to parse JSON from LLM response with cleanup."""
    # Extract JSON from markdown code blocks
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0]
    elif '```' in content:
        content = content.split('```')[1].split('```')[0]
    
    content = content.strip()
    
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    
    # Try fixing common JSON issues: trailing commas
    import re
    cleaned = re.sub(r',\s*([}\]])', r'\1', content)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    
    return None


def generate_summary(client: OpenAI, prompt: str, news_data: dict, max_retries: int = 3) -> dict:
    """Call LLM to generate summary with retry on JSON parse errors."""
    user_content = f"""以下是今日采集的新闻数据：

```json
{json.dumps(news_data, ensure_ascii=False, indent=2)}
```

请根据 prompt 要求生成 Data+AI 全球日报。只输出 JSON，不要有其他内容。"""

    last_error = None
    for attempt in range(1, max_retries + 1):
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
            result = try_parse_json(content)
            if result is not None:
                return result
            
            last_error = f"Failed to parse JSON from LLM response (attempt {attempt}/{max_retries})"
            print(f"{last_error}")
            print(f"Response preview: {content[:200]}...")
        except json.JSONDecodeError as e:
            last_error = f"JSON parse error (attempt {attempt}/{max_retries}): {e}"
            print(last_error)
        except Exception as e:
            last_error = f"LLM API error (attempt {attempt}/{max_retries}): {e}"
            print(last_error)
    
    raise RuntimeError(f"Failed after {max_retries} attempts. Last error: {last_error}")


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
    print(f"Loaded {items_count} items from raw_news.json")
    
    # If no items, create empty summary
    if items_count == 0:
        print("Warning: No news items found, creating empty summary")
        summary = {
            'date': news_data.get('date', ''),
            'sections': [],
            'total_items': 0
        }
    else:
        # Compress data to fit LLM token limits
        compressed_data = compress_news_data(news_data)
        print(f"Compressed to {compressed_data['included_in_summary']} items for LLM")
        
        # Generate summary
        summary = generate_summary(client, prompt, compressed_data)
    
    # Save output
    with open('summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    
    print("Summary saved to summary.json")


if __name__ == '__main__':
    main()
