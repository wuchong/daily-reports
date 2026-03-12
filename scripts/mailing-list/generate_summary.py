#!/usr/bin/env python3
"""Generate summaries for discussions, votes, and JIRA using LLM.

Environment variables:
- PROJECT_NAME: Project display name (e.g., Flink, Iceberg, Kafka, Spark)
- OPENAI_BASE_URL: OpenAI API base URL
- OPENAI_API_KEY: OpenAI API key
"""

import json
import os
from pathlib import Path

from openai import OpenAI


def load_prompt() -> str:
    """Load prompt template."""
    prompt_path = Path(__file__).parent.parent.parent / "prompts" / "mailing-list-summarize.md"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def create_client() -> OpenAI:
    """Create OpenAI client with custom base URL if configured."""
    return OpenAI(
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY")
    )


def extract_author_name(from_field: str) -> str:
    """Extract author name from email 'from' field."""
    # Format: "Name <email>" or just "email"
    if "<" in from_field:
        return from_field.split("<")[0].strip().strip('"')
    return from_field.split("@")[0]


def summarize_discussion(client: OpenAI, discussion: dict, project_name: str) -> dict:
    """Generate summary for a discussion thread."""
    emails = discussion.get("emails", [])
    
    # Build email content for LLM
    email_texts = []
    for email in emails[:15]:  # Limit to first 15 emails
        author = extract_author_name(email.get("from", ""))
        body = email.get("body", "")[:2000]  # Truncate long emails
        email_texts.append(f"From: {author}\n{body}")
    
    content = "\n\n---\n\n".join(email_texts)
    
    prompt = f"""请根据以下 {project_name} 社区邮件讨论内容，生成简洁的中文摘要。

要求：
1. 用 2-3 句话概括讨论的核心议题和进展
2. 列出主要参与者的关键观点（最多 3 个）
3. 如有初步结论或下一步行动，请指出

输出 JSON 格式：
{{"summary": "...", "key_points": [{{"author": "...", "point": "..."}}], "conclusion": "..."}}

讨论主题: {discussion.get('subject', '')}

邮件内容:
{content}"""

    try:
        response = client.chat.completions.create(
            model="glm-5",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error summarizing discussion '{discussion.get('subject', '')}': {e}")
        return {"summary": "摘要生成失败", "key_points": [], "conclusion": ""}


def summarize_objection(client: OpenAI, vote: dict, project_name: str) -> str:
    """Generate summary for vote objections."""
    objection_emails = vote.get("objection_emails", [])
    if not objection_emails:
        return ""
    
    # Build objection content
    objection_texts = []
    for email in objection_emails[:5]:
        author = extract_author_name(email.get("from", ""))
        body = email.get("body", "")[:1000]
        objection_texts.append(f"From: {author}\n{body}")
    
    content = "\n\n---\n\n".join(objection_texts)
    
    prompt = f"""请根据以下 {project_name} 社区投票回复，简述异议原因（1-2 句话）。

投票主题: {vote.get('subject', '')}

异议内容:
{content}

输出 JSON 格式：
{{"objection_summary": "xxx 提出 -1，原因是..."}}"""

    try:
        response = client.chat.completions.create(
            model="glm-5",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("objection_summary", "")
    except Exception as e:
        print(f"Error summarizing objection for '{vote.get('subject', '')}': {e}")
        return ""


def analyze_vote_result(client: OpenAI, vote: dict, project_name: str) -> dict:
    """Analyze vote result email to determine if passed or failed."""
    result_email = vote.get("result_email", {})
    if not result_email:
        return {"status": "passed", "reason": ""}
    
    subject = result_email.get("subject", "")
    body = result_email.get("body", "")[:1500]
    
    prompt = f"""请分析以下 {project_name} 社区投票结果邮件，判断投票是否通过。

投票主题: {vote.get('subject', '')}
结果邮件标题: {subject}
结果邮件内容:
{body}

请分析并输出 JSON 格式：
{{
  "passed": true/false,
  "reason": "如果未通过，简要说明原因（一句话）；如果通过则留空"
}}"""

    try:
        response = client.chat.completions.create(
            model="glm-5",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return {
            "status": "passed" if result.get("passed", True) else "failed",
            "reason": result.get("reason", "")
        }
    except Exception as e:
        print(f"Error analyzing vote result for '{vote.get('subject', '')}': {e}")
        return {"status": "passed", "reason": ""}


def summarize_jira(client: OpenAI, jira_titles: list[str], project_name: str) -> str:
    """Generate summary for JIRA issues."""
    if not jira_titles:
        return "本周无新建 JIRA。"
    
    titles_text = "\n".join(f"- {t}" for t in jira_titles[:50])  # Limit to 50 titles
    
    prompt = f"""请根据以下 {project_name} 社区 JIRA 邮件标题列表，生成 2-3 句话的整体摘要，概括本周 JIRA 主要涉及哪些方面。

JIRA 标题列表:
{titles_text}

输出 JSON 格式：
{{"jira_summary": "本周 JIRA 主要集中在..."}}"""

    try:
        response = client.chat.completions.create(
            model="glm-5",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        result = json.loads(response.choices[0].message.content)
        return result.get("jira_summary", "")
    except Exception as e:
        print(f"Error summarizing JIRA: {e}")
        return "JIRA 摘要生成失败"


def main():
    """Main entry point."""
    project_name = os.environ.get("PROJECT_NAME", "Apache")
    
    # Load threads data
    with open("threads.json", "r", encoding="utf-8") as f:
        threads = json.load(f)
    
    client = create_client()
    
    # Summarize discussions (top 10 by reply count)
    print(f"Summarizing {project_name} discussions...")
    discussions = threads.get("discussions", [])[:10]
    for i, discussion in enumerate(discussions):
        print(f"  [{i+1}/{len(discussions)}] {discussion.get('subject', '')[:50]}...")
        summary = summarize_discussion(client, discussion, project_name)
        discussion["llm_summary"] = summary
        # Remove full emails to reduce file size
        discussion.pop("emails", None)
    threads["discussions"] = discussions
    
    # Summarize vote objections and analyze results
    print("Processing votes...")
    for vote in threads.get("votes", []):
        if vote.get("status") == "has_result":
            # Analyze vote result using LLM
            print(f"  Analyzing result for: {vote.get('subject', '')[:50]}...")
            result = analyze_vote_result(client, vote, project_name)
            vote["status"] = result["status"]  # "passed" or "failed"
            vote["fail_reason"] = result["reason"]
        elif vote.get("has_objection"):
            # Summarize objections for in-progress votes
            print(f"  Processing objection for: {vote.get('subject', '')[:50]}...")
            vote["objection_summary"] = summarize_objection(client, vote, project_name)
        
        # Cleanup
        vote.pop("objection_emails", None)
        vote.pop("result_email", None)
    
    # Summarize JIRA
    print("Summarizing JIRA...")
    threads["jira_summary"] = summarize_jira(client, threads.get("jira_titles", []), project_name)
    
    # Save summary
    with open("summary.json", "w", encoding="utf-8") as f:
        json.dump(threads, f, ensure_ascii=False, indent=2)
    
    print("Summary saved to summary.json")


if __name__ == "__main__":
    main()
