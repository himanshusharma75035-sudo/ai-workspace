from __future__ import annotations

import re

from .config import settings


def words(prompt: str) -> set[str]:
    return set(re.findall(r"[\w]+", prompt.lower(), flags=re.UNICODE))


def is_hinglish(prompt: str) -> bool:
    lowered = prompt.lower()
    tokens = words(prompt)
    markers = {
        "aap", "aur", "batao", "hai", "hain", "ka", "karo", "karta",
        "ke", "ki", "kya", "mein", "mujhe", "samjhao", "se", "yeh",
    }
    return "hinglish" in lowered or len(tokens & markers) >= 2


def is_greeting(prompt: str) -> bool:
    normalized = re.sub(r"[^\w\u0900-\u097f]+", " ", prompt.lower()).strip()
    return normalized in {
        "hi", "hello", "hey", "good morning", "good afternoon",
        "good evening", "namaste", "namaskar", "\u0928\u092e\u0938\u094d\u0924\u0947",
        "\u0928\u092e\u0938\u094d\u0915\u093e\u0930",
    }


def is_broad_organization_overview(prompt: str) -> bool:
    lowered = prompt.lower()
    tokens = words(prompt)
    aliases = settings.organization_aliases
    if not any(alias in lowered for alias in aliases):
        return False
    umbrella = bool(tokens & {"business", "businesses", "company", "ecosystem", "overview"})
    alias_tokens = {
        token
        for alias in aliases
        for token in re.findall(r"[\w]+", alias, flags=re.UNICODE)
    }
    generic_tokens = {
        "about", "actually", "do", "does", "explain", "is", "me", "tell", "the", "what",
    }
    if tokens - alias_tokens - generic_tokens and not umbrella:
        return False
    normalized = re.sub(r"[^\w]+", " ", lowered, flags=re.UNICODE).strip()
    patterns = []
    for alias in aliases:
        patterns.extend(
            (
                f"what is {alias}", f"what does {alias} do",
                f"what {alias} actually does", f"{alias} actually kya karta hai",
                f"{alias} kya hai", f"about {alias}", f"{alias} business",
                f"{alias} company", f"{alias} overview", f"{alias} ecosystem",
            )
        )
    return umbrella or normalized in patterns

def contextualize_retrieval_query(prompt: str, history: list[dict[str, str]]) -> str:
    tokens = words(prompt)
    followup_markers = {
        "above", "again", "details", "else", "explain", "it", "more",
        "that", "them", "they", "this", "those", "why",
    }
    if len(tokens) > 10 or not (tokens & followup_markers):
        return prompt
    previous_user = next(
        (item["content"] for item in reversed(history) if item.get("role") == "user"),
        "",
    )
    return f"{previous_user} {prompt}".strip() if previous_user else prompt
