from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import settings
from app.database import control_db
from app.knowledge import knowledge

SOURCES = [(item["title"], item["url"]) for item in settings.knowledge_sources]
ALLOWED_HOSTS = {(urlparse(url).hostname or "").lower() for _, url in SOURCES}


def html_to_text(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    descriptions = [
        node.get("content", "")
        for node in soup.find_all("meta")
        if node.get("name", "").lower() in {"description", "keywords"}
    ]
    body = soup.get_text("\n", strip=True)
    return "\n\n".join(part for part in [title, *descriptions, body] if part)


def fetch(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError(f"Host is not approved: {host}")
    headers = {"User-Agent": "OpenSourceInternalRAG/0.1 (+approved internal prototype)"}
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
    if "text/html" in response.headers.get("content-type", ""):
        return html_to_text(response.text)
    return response.text


def main() -> int:
    if not SOURCES:
        print("No website sources are configured. Set KNOWLEDGE_SOURCES_JSON in .env.")
        return 0
    control_db.initialize()
    knowledge.initialize()
    failures = 0
    for title, url in SOURCES:
        try:
            result = knowledge.add_document("public", title, url, fetch(url))
            print(f"{title}: {result['status']} ({result['chunks']} chunks)")
        except Exception as exc:
            failures += 1
            print(f"{title}: FAILED: {exc}")
    return 1 if failures == len(SOURCES) else 0


if __name__ == "__main__":
    raise SystemExit(main())
