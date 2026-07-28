from __future__ import annotations

import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]


def _load_env(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_env(ROOT_DIR / ".env")

TEAMS = (
    "public",
    "business",
    "operations",
    "finance",
    "accounts",
    "customer_support",
    "engineering",
    "hr",
    "legal_compliance",
)

@dataclass(frozen=True)
class Settings:
    organization_name: str = os.getenv("ORGANIZATION_NAME", "Your Organization")
    assistant_name: str = os.getenv("ASSISTANT_NAME", "OpenSource AI Workspace")
    organization_initial: str = os.getenv("ORGANIZATION_INITIAL", "O")[:1].upper()
    organization_aliases_raw: str = os.getenv("ORGANIZATION_ALIASES", "your organization")
    app_name: str = os.getenv("APP_NAME", os.getenv("ASSISTANT_NAME", "OpenSource AI Workspace"))
    app_mode: str = os.getenv("APP_MODE", "demo")
    allowed_email_domain: str = os.getenv("ALLOWED_EMAIL_DOMAIN", "company.example").lower()
    session_secret: str = os.getenv("SESSION_SECRET") or secrets.token_urlsafe(32)
    session_cookie_name: str = os.getenv("SESSION_COOKIE_NAME", "ai_workspace_session")
    cookie_secure: bool = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    app_host: str = os.getenv("APP_HOST", "127.0.0.1")
    app_port: int = int(os.getenv("APP_PORT", "8181"))
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11445")
    ollama_text_model: str = os.getenv("OLLAMA_TEXT_MODEL", "qwen3:4b")
    ollama_fallback_model: str = os.getenv("OLLAMA_FALLBACK_MODEL", "qwen3:1.7b")
    ollama_embedding_model: str = os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma")
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "10"))
    service_controls_enabled: bool = (
        os.getenv("ENABLE_SERVICE_CONTROLS", "false").lower() == "true"
    )
    service_control_key: str = os.getenv("SERVICE_CONTROL_KEY", "")
    knowledge_sources_json: str = os.getenv("KNOWLEDGE_SOURCES_JSON", "[]")

    @property
    def organization_aliases(self) -> tuple[str, ...]:
        values = [self.organization_name, *self.organization_aliases_raw.split(",")]
        return tuple(dict.fromkeys(value.strip().lower() for value in values if value.strip()))

    @property
    def knowledge_sources(self) -> list[dict[str, str]]:
        try:
            parsed: Any = json.loads(self.knowledge_sources_json)
        except json.JSONDecodeError as exc:
            raise ValueError("KNOWLEDGE_SOURCES_JSON must be valid JSON") from exc
        if not isinstance(parsed, list):
            raise ValueError("KNOWLEDGE_SOURCES_JSON must be a JSON list")
        sources: list[dict[str, str]] = []
        for item in parsed:
            if not isinstance(item, dict):
                raise ValueError("Each knowledge source must be a JSON object")
            title = str(item.get("title", "")).strip()
            url = str(item.get("url", "")).strip()
            if not title or not url:
                raise ValueError("Each knowledge source needs non-empty title and url values")
            sources.append({"title": title, "url": url})
        return sources

    @property
    def public_branding(self) -> dict[str, str]:
        return {
            "organization_name": self.organization_name,
            "assistant_name": self.assistant_name,
            "organization_initial": self.organization_initial,
            "allowed_email_domain": self.allowed_email_domain,
        }

    @property
    def data_dir(self) -> Path:
        return ROOT_DIR / "data"

    @property
    def control_db_path(self) -> Path:
        return self.data_dir / "control.db"

    @property
    def knowledge_dir(self) -> Path:
        return self.data_dir / "knowledge"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"


settings = Settings()
