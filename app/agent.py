"""
Step 3: Agent logic.

Ties together:
  - CatalogRetriever (semantic search over 369 SHL assessments)
  - Groq LLM (generates reply - fast, generous free tier)
  - Gemini embeddings (only for retrieval, not chat)
  - Prompts (system prompt with catalog results injected)

The agent is stateless — full conversation history arrives on every
call. No server-side session storage.
"""

import os
from dotenv import load_dotenv
from pathlib import Path
from groq import Groq

REPO_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=REPO_ROOT / ".env")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

from retriever import CatalogRetriever
from prompts import SYSTEM_PROMPT
from schemas import Recommendation

# Load retriever once at import time (embeddings loaded into memory)
_retriever = CatalogRetriever()
_groq_client = Groq(api_key=GROQ_API_KEY)


def _build_query_from_history(messages: list[dict]) -> str:
    """Concatenate all user messages into a single retrieval query."""
    user_turns = [m["content"] for m in messages if m["role"] == "user"]
    return " ".join(user_turns)


def _format_conversation(messages: list[dict]) -> str:
    """Format conversation history for injection into system prompt."""
    lines = []
    for m in messages:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    return "\n".join(lines)


def _format_catalog_results(results: list[dict]) -> str:
    """Format catalog search results for injection into system prompt."""
    if not results:
        return "No catalog results found."
    lines = []
    for r in results:
        test_type = r.get("test_type", [])
        if isinstance(test_type, list):
            test_type = ", ".join(test_type)
        lines.append(
            f"- Name: {r['name']}\n"
            f"  URL: {r['url']}\n"
            f"  Type: {test_type}\n"
            f"  Description: {r.get('description', '')}\n"
            f"  Job Levels: {', '.join(r.get('job_levels', []))}\n"
            f"  Keys: {', '.join(r.get('keys', []))}\n"
            f"  Remote: {r.get('remote_testing', False)} | "
            f"Adaptive: {r.get('adaptive', False)} | "
            f"Duration: {r.get('duration', 'N/A')}"
        )
    return "\n".join(lines)


def _is_vague(messages: list[dict]) -> bool:
    """Return True only if query is genuinely too vague to act on."""
    user_turns = [m for m in messages if m["role"] == "user"]
    if len(user_turns) > 1:
        return False
    if not user_turns:
        return True
    first = user_turns[0]["content"].strip()
    if len(first.split()) >= 8:
        return False
    has_signal = any(w in first.lower() for w in [
        "developer", "engineer", "manager", "analyst", "sales", "designer",
        "nurse", "accountant", "java", "python", "javascript", "angular",
        "sql", "aws", "docker", "spring", "data", "customer", "service",
        "marketing", "finance", "hr", "graduate", "intern", "leadership",
        "executive", "director", "cxo", "senior", "junior", "entry",
        "contact", "centre", "center", "admin", "operator", "plant",
        "safety", "healthcare", "medical", "hipaa", "excel", "word",
        "personality", "cognitive", "numerical", "verbal", "reasoning",
        "situational", "judgment", "behaviour", "behavior", "skill",
        "hiring", "recruit", "assess", "screen", "test", "battery",
        "jd", "role", "position"
    ])
    return not has_signal


def _count_turns(messages: list[dict]) -> int:
    return len(messages)


def _call_groq(system_prompt: str, messages: list[dict]) -> str:
    """Call Groq LLM with system prompt + conversation history."""
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY not set.")

    groq_messages = [{"role": "system", "content": system_prompt}]
    for m in messages:
        groq_messages.append({
            "role": m["role"],
            "content": m["content"]
        })

    response = _groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=groq_messages,
        temperature=0.3,
        max_tokens=1024,
    )

    return response.choices[0].message.content


def _extract_recommendations(
    reply_text: str,
    catalog_results: list[dict],
) -> list[Recommendation]:
    """Match assessment names mentioned in reply against catalog results.
    Uses both exact and partial matching to handle LLM paraphrasing.
    Only returns real catalog items — never invented ones."""
    recommendations = []
    reply_lower = reply_text.lower()
    seen = set()

    for item in catalog_results:
        name = item["name"]
        name_lower = name.lower()

        # Strategy 1: exact name match
        matched = name_lower in reply_lower

        # Strategy 2: partial match — strip parenthetical suffixes like "(New)"
        # e.g. "Core Java" matches "Core Java (Entry Level) (New)"
        if not matched:
            core_name = name_lower.split("(")[0].strip()
            if len(core_name) > 5 and core_name in reply_lower:
                matched = True

        if matched and name not in seen:
            seen.add(name)
            test_type = item.get("test_type", [])
            if isinstance(test_type, list):
                test_type_str = ", ".join(test_type)
            else:
                test_type_str = str(test_type)
            recommendations.append(Recommendation(
                name=name,
                url=item["url"],
                test_type=test_type_str,
            ))

    return recommendations[:10]


def _should_end_conversation(reply_text: str, recommendations: list) -> bool:
    if not recommendations:
        return False
    end_signals = [
        "good luck", "best of luck", "hope this helps",
        "let me know if you need", "feel free to ask",
        "happy to help", "is there anything else",
        "that completes", "here is your shortlist",
        "here are your", "final recommendation"
    ]
    reply_lower = reply_text.lower()
    return any(signal in reply_lower for signal in end_signals)


def chat(messages: list[dict]) -> dict:
    """
    Main agent entry point.

    Args:
        messages: list of {"role": "user"|"assistant", "content": str}

    Returns:
        {"reply": str, "recommendations": list, "end_of_conversation": bool}
    """
    # Enforce turn cap (8 turns max per spec)
    if _count_turns(messages) >= 8:
        return {
            "reply": "We've reached the maximum conversation length. I hope the assessments I recommended are helpful! Feel free to start a new conversation if you need further assistance.",
            "recommendations": [],
            "end_of_conversation": True,
        }

    query = _build_query_from_history(messages)

    # Primary semantic search on the full query
    primary_results = _retriever.search(query, top_k=12)
    seen_names = {r["name"] for r in primary_results}

    # Always pull OPQ32r and Verify into context — they appear in nearly
    # every trace and can be missed when query is skill-specific
    supplemental_results = []
    for supplement_query in [
        "Occupational Personality Questionnaire OPQ32r personality behavior",
        "SHL Verify Interactive G+ cognitive ability reasoning",
        "SHL Verify Interactive Numerical Reasoning aptitude",
        "SHL Verify Interactive Deductive Inductive Reasoning",
    ]:
        for r in _retriever.search(supplement_query, top_k=3):
            if r["name"] not in seen_names:
                seen_names.add(r["name"])
                supplemental_results.append(r)

    catalog_results = primary_results + supplemental_results

    conversation_text = _format_conversation(messages)
    catalog_text = _format_catalog_results(catalog_results)

    vague_note = ""
    if _is_vague(messages):
        vague_note = (
            "\n\nIMPORTANT: The user's query is too vague to recommend yet. "
            "Ask ONE clarifying question about the role or seniority level. "
            "Do NOT recommend any assessments yet."
        )

    full_prompt = SYSTEM_PROMPT.format(
        catalog_results=catalog_text,
        conversation=conversation_text,
    ) + vague_note

    reply_text = _call_groq(full_prompt, messages)

    recommendations = _extract_recommendations(reply_text, catalog_results)

    if _is_vague(messages):
        recommendations = []

    end_of_conv = _should_end_conversation(reply_text, recommendations)

    return {
        "reply": reply_text,
        "recommendations": [r.model_dump() for r in recommendations],
        "end_of_conversation": end_of_conv,
    }