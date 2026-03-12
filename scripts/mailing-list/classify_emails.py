#!/usr/bin/env python3
"""Classify emails into categories: Announce, Vote, Discussion, JIRA.

This script is project-agnostic and works with any Apache mailing list.
"""

import json
import re
from collections import defaultdict


# Classification patterns (priority order: JIRA > Announce > Vote > Discussion)
PATTERNS = {
    "jira": re.compile(r"\[jira\]", re.IGNORECASE),
    "announce": re.compile(r"\[ANNOUNCE\]", re.IGNORECASE),
    "vote": re.compile(r"\[(VOTE|RESULT)\]", re.IGNORECASE),
    "discuss": re.compile(r"\[DISCUSS\]", re.IGNORECASE),
}

# Objection patterns for votes
OBJECTION_PATTERNS = re.compile(r"(?:^|\s)([+-]0|-1)(?:\s|$|,|\.)")


def clean_subject(subject: str) -> str:
    """Remove classification tags from subject."""
    cleaned = subject
    for pattern in PATTERNS.values():
        cleaned = pattern.sub("", cleaned)
    # Remove Re:/Fwd:/FW: prefix for display
    cleaned = re.sub(r"^((Re:|Fwd:|FW:)\s*)+", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def get_thread_root(subject: str) -> str:
    """Extract thread root subject (remove Re:/Fwd:/FW: prefix and tags)."""
    cleaned = subject
    # Remove Re:/Fwd:/FW: prefix
    cleaned = re.sub(r"^((Re:|Fwd:|FW:)\s*)+", "", cleaned, flags=re.IGNORECASE)
    # Remove classification tags for grouping
    for pattern in PATTERNS.values():
        cleaned = pattern.sub("", cleaned)
    return cleaned.strip()


def classify_email(subject: str) -> str:
    """Classify email by subject. Returns category name."""
    # Priority order
    if PATTERNS["jira"].search(subject):
        return "jira"
    if PATTERNS["announce"].search(subject):
        return "announce"
    if PATTERNS["vote"].search(subject):
        return "vote"
    # Everything else is discussion (including [DISCUSS] tagged)
    return "discussion"


def has_objection(body: str) -> bool:
    """Check if email body contains voting objection (-1, +0, -0)."""
    if not body:
        return False
    # Check first few lines where votes typically appear
    lines = body.split("\n")[:20]
    text = "\n".join(lines)
    return bool(OBJECTION_PATTERNS.search(text))


def build_thread_link(mid: str) -> str:
    """Build permalink for email thread."""
    return f"https://lists.apache.org/thread/{mid}"


def group_into_threads(emails: list[dict]) -> dict[str, list[dict]]:
    """Group emails by thread root subject."""
    threads = defaultdict(list)
    for email in emails:
        subject = email.get("subject", "")
        root = get_thread_root(subject)
        threads[root].append(email)
    return dict(threads)


def process_emails(raw_data: dict) -> dict:
    """Process raw emails into categorized threads."""
    emails = raw_data.get("emails", [])
    
    # Classify all emails
    categorized = {
        "announce": [],
        "vote": [],
        "discussion": [],
        "jira": []
    }
    
    for email in emails:
        subject = email.get("subject", "")
        category = classify_email(subject)
        categorized[category].append(email)
    
    # Process each category
    result = {
        "week": raw_data.get("week"),
        "date_range": raw_data.get("date_range"),
        "announcements": [],
        "votes": [],
        "discussions": [],
        "jira_count": len(categorized["jira"]),
        "jira_titles": [e.get("subject", "") for e in categorized["jira"]]
    }
    
    # Announcements: group by thread, take root email
    announce_threads = group_into_threads(categorized["announce"])
    for root_subject, thread_emails in announce_threads.items():
        # Sort by epoch to get first email
        thread_emails.sort(key=lambda e: e.get("epoch", 0))
        root_email = thread_emails[0]
        result["announcements"].append({
            "subject": clean_subject(root_subject),
            "link": build_thread_link(root_email.get("mid", "")),
            "from": root_email.get("from", ""),
            "date": root_email.get("date", "")
        })
    
    # Votes: group by thread, check for objections
    vote_threads = group_into_threads(categorized["vote"])
    for root_subject, thread_emails in vote_threads.items():
        thread_emails.sort(key=lambda e: e.get("epoch", 0))
        root_email = thread_emails[0]
        
        # Check for objections in replies
        objection_emails = []
        for email in thread_emails[1:]:  # Skip root
            body = email.get("body", "")
            if has_objection(body):
                objection_emails.append({
                    "from": email.get("from", ""),
                    "body": body,
                    "mid": email.get("mid", "")
                })
        
        result["votes"].append({
            "subject": clean_subject(root_subject),
            "link": build_thread_link(root_email.get("mid", "")),
            "from": root_email.get("from", ""),
            "date": root_email.get("date", ""),
            "reply_count": len(thread_emails) - 1,
            "has_objection": len(objection_emails) > 0,
            "objection_emails": objection_emails
        })
    
    # Discussions: group by thread
    discussion_threads = group_into_threads(categorized["discussion"])
    for root_subject, thread_emails in discussion_threads.items():
        thread_emails.sort(key=lambda e: e.get("epoch", 0))
        root_email = thread_emails[0]
        
        # Collect participants
        participants = list(set(e.get("from", "") for e in thread_emails))
        
        result["discussions"].append({
            "subject": clean_subject(root_subject),
            "link": build_thread_link(root_email.get("mid", "")),
            "from": root_email.get("from", ""),
            "date": root_email.get("date", ""),
            "reply_count": len(thread_emails) - 1,
            "participants": participants,
            "emails": thread_emails  # Full emails for LLM summarization
        })
    
    # Sort discussions by reply count (most active first)
    result["discussions"].sort(key=lambda d: d["reply_count"], reverse=True)
    
    return result


def main():
    """Main entry point."""
    # Load raw emails
    with open("raw_emails.json", "r", encoding="utf-8") as f:
        raw_data = json.load(f)
    
    print(f"Processing {len(raw_data.get('emails', []))} emails...")
    
    # Process and classify
    threads = process_emails(raw_data)
    
    print(f"Categories:")
    print(f"  - Announcements: {len(threads['announcements'])}")
    print(f"  - Votes: {len(threads['votes'])}")
    print(f"  - Discussions: {len(threads['discussions'])}")
    print(f"  - JIRA: {threads['jira_count']}")
    
    # Save to file
    with open("threads.json", "w", encoding="utf-8") as f:
        json.dump(threads, f, ensure_ascii=False, indent=2)
    
    print("Saved to threads.json")


if __name__ == "__main__":
    main()
