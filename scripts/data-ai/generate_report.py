#!/usr/bin/env python3
"""Generate HTML report from summary."""

import json
import os
import re
from pathlib import Path


GITHUB_PAGES_URL = os.environ.get('GITHUB_PAGES_URL', 'https://example.github.io/daily-reports')


def load_summary():
    """Load summary data."""
    with open('summary.json', 'r', encoding='utf-8') as f:
        return json.load(f)


def render_sources(sources: list) -> str:
    """Render source links."""
    if not sources:
        return ''
    links = [f'<a href="{s["url"]}">{s["name"]}</a>' for s in sources]
    return f'<p class="sources">📌 {" | ".join(links)}</p>'


def strip_impact_prefix(text: str) -> str:
    """Remove duplicate impact prefix if LLM already included it."""
    return re.sub(r'^(📊\s*)?(数据平台影响[：:]\s*)?', '', text)


def render_news_item(item: dict) -> str:
    """Render a single news item."""
    impact = strip_impact_prefix(item.get('data_platform_impact', ''))
    return f'''
    <article class="news-item">
        <h3>{item.get('title', '')}</h3>
        {render_sources(item.get('sources', []))}
        <p class="date">{item.get('date', '')}</p>
        <p class="summary">{item.get('summary', '')}</p>
        <div class="impact">📊 数据平台影响：{impact}</div>
    </article>'''


def render_analyst_item(item: dict) -> str:
    """Render analyst insight item."""
    return f'''
    <article class="analyst-item">
        <h3>{item.get("title", "")}</h3>
        <p class="meta">来源: {item.get("source", "")} - {item.get("report", "")}</p>
        <p class="key-data"><strong>关键数据：</strong>{item.get("key_data", "")}</p>
        <p class="implication"><strong>启示：</strong>{item.get("implication", "")}</p>
    </article>'''


def render_watchlist_item(item: dict) -> str:
    """Render watchlist item."""
    return f'''
    <article class="watchlist-item">
        <h3>{item.get("signal", "")}</h3>
        <span class="status">{item.get("status", "待观察")}</span>
        <p class="reason">{item.get("reason", "")}</p>
        <p class="milestone"><strong>下一里程碑：</strong>{item.get("next_milestone", "")}</p>
    </article>'''


def render_stock_item(item: dict) -> str:
    """Render stock analysis item."""
    signal = item.get('signal', 'neutral')
    signal_class = f'signal-{signal}'
    signal_text = {'bullish': '🟢 看多', 'bearish': '🔴 看空', 'neutral': '⚪ 中性'}.get(signal, '⚪ 中性')
    
    catalysts = item.get('catalysts', [])
    risks = item.get('risks', [])
    catalysts_html = ''.join(f'<li>{c}</li>' for c in catalysts) if catalysts else '<li>暂无</li>'
    risks_html = ''.join(f'<li>{r}</li>' for r in risks) if risks else '<li>暂无</li>'
    
    return f'''
    <article class="stock-item">
        <div class="stock-header">
            <span class="ticker">{item.get('ticker', '')}</span>
            <span class="company">{item.get('company', '')}</span>
            <span class="signal {signal_class}">{signal_text}</span>
        </div>
        <p class="stock-summary">{item.get('summary', '')}</p>
        <div class="stock-details">
            <div class="catalysts">
                <strong>🚀 催化剂</strong>
                <ul>{catalysts_html}</ul>
            </div>
            <div class="risks">
                <strong>⚠️ 风险</strong>
                <ul>{risks_html}</ul>
            </div>
        </div>
    </article>'''


def generate_html(summary: dict) -> str:
    """Generate full HTML report."""
    date = summary.get('date', '')
    sections = summary.get('sections', {})
    
    # Render top 3 changes
    top_changes_html = ''.join(
        f'<li><strong>{c.get("title", "")}</strong> — {c.get("summary", "")}</li>'
        for c in summary.get('top_3_changes', [])
    )
    
    # Render sections
    top_signals_html = ''.join(render_news_item(item) for item in sections.get('top_signals', []))
    product_tech_html = ''.join(render_news_item(item) for item in sections.get('product_tech', []))
    people_views_html = ''.join(render_news_item(item) for item in sections.get('people_views', []))
    analyst_html = ''.join(render_analyst_item(item) for item in sections.get('analyst_insights', []))
    watchlist_html = ''.join(render_watchlist_item(item) for item in sections.get('watchlist', []))
    stock_html = ''.join(render_stock_item(item) for item in sections.get('stock_analysis', []))
    
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data+AI 全球日报 | {date}</title>
    <link rel="stylesheet" href="../assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <nav class="back-link"><a href="../index.html">← 返回列表</a></nav>
            <h1>Data+AI 全球日报 | {date}</h1>
        </header>

        <section class="top-changes">
            <h2>🔥 今日最重要的3个变化</h2>
            <ol>{top_changes_html}</ol>
            <p class="judgment"><strong>总判断：</strong>{summary.get("overall_judgment", "")}</p>
        </section>

        <section class="top-signals">
            <h2>📡 重要信号</h2>
            {top_signals_html if top_signals_html else '<p class="empty">暂无</p>'}
        </section>

        <section class="product-tech">
            <h2>💻 产品与技术</h2>
            {product_tech_html if product_tech_html else '<p class="empty">暂无</p>'}
        </section>

        <section class="people-views">
            <h2>👤 人物与观点</h2>
            {people_views_html if people_views_html else '<p class="empty">暂无</p>'}
        </section>

        <section class="analyst-insights">
            <h2>📊 分析师洞察</h2>
            {analyst_html if analyst_html else '<p class="empty">暂无</p>'}
        </section>

        <section class="watchlist">
            <h2>👀 观察列表</h2>
            {watchlist_html if watchlist_html else '<p class="empty">暂无</p>'}
        </section>

        <section class="stock-analysis">
            <h2>📈 股票分析</h2>
            <p class="disclaimer">⚠️ 以下内容仅供参考，不构成任何投资建议。投资有风险，入市需谨慎。</p>
            {stock_html if stock_html else '<p class="empty">暂无相关股票分析</p>'}
        </section>

        <footer>
            <p>Generated by Data+AI Daily Report System</p>
        </footer>
    </div>
</body>
</html>'''


def update_index(date: str):
    """Update index.html with report list."""
    reports_dir = Path('docs/data-ai/reports')
    reports_dir.mkdir(parents=True, exist_ok=True)
    
    # Get all reports
    reports = sorted([f.stem for f in reports_dir.glob('*.html')], reverse=True)
    
    # Group by month
    months = {}
    for d in reports:
        month = d[:7]
        if month not in months:
            months[month] = []
        months[month].append(d)
    
    # Generate HTML
    sections = ''
    for month, dates in sorted(months.items(), reverse=True):
        items = ''.join(f'<li><a href="reports/{d}.html">{d}</a></li>' for d in sorted(dates, reverse=True))
        sections += f'<section class="month"><h2>📅 {month}</h2><ul>{items}</ul></section>'
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data+AI Daily Reports</title>
    <link rel="stylesheet" href="assets/style.css">
</head>
<body>
    <div class="container">
        <header>
            <h1>Data+AI 全球日报</h1>
            <p>Data+AI 领域每日动态归档</p>
        </header>
        {sections if sections else '<p>暂无报告</p>'}
    </div>
</body>
</html>'''
    
    with open('docs/data-ai/index.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Index updated: docs/data-ai/index.html")


def main():
    """Main entry point."""
    summary = load_summary()
    date = summary.get('date', '')
    
    # Generate HTML
    html = generate_html(summary)
    
    # Save report
    output_dir = Path('docs/data-ai/reports')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f'{date}.html'
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Report saved to {output_path}")
    
    # Update index
    update_index(date)


if __name__ == '__main__':
    main()
