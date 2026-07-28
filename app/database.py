from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import TEAMS, settings


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ControlDatabase:
    def __init__(self, path: Path):
        self.path = path
        self._init_lock = threading.Lock()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        with self._init_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.connect() as db:
                db.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        email TEXT NOT NULL UNIQUE,
                        display_name TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'member',
                        approved INTEGER NOT NULL DEFAULT 0,
                        requested_team TEXT,
                        assigned_team TEXT NOT NULL DEFAULT 'public',
                        preferred_language TEXT NOT NULL DEFAULT 'English',
                        role_title TEXT,
                        onboarding_complete INTEGER NOT NULL DEFAULT 0,
                        profile_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        conversation_id TEXT NOT NULL,
                        user_email TEXT NOT NULL,
                        message_role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        metadata_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT NOT NULL,
                        user_email TEXT NOT NULL,
                        title TEXT NOT NULL DEFAULT 'New conversation',
                        archived INTEGER NOT NULL DEFAULT 0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        PRIMARY KEY (id, user_email)
                    );

                    CREATE TABLE IF NOT EXISTS message_feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        message_id INTEGER NOT NULL,
                        user_email TEXT NOT NULL,
                        rating TEXT NOT NULL CHECK (rating IN ('helpful', 'not_helpful')),
                        comment TEXT NOT NULL DEFAULT '',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE (message_id, user_email),
                        FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS action_requests (
                        id TEXT PRIMARY KEY,
                        user_email TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        status TEXT NOT NULL,
                        result_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS audit_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_email TEXT,
                        event_type TEXT NOT NULL,
                        details_json TEXT NOT NULL DEFAULT '{}',
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_messages_conversation_user
                    ON messages (conversation_id, user_email, id);

                    CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
                    ON conversations (user_email, archived, updated_at DESC);

                    CREATE INDEX IF NOT EXISTS idx_feedback_rating
                    ON message_feedback (rating, created_at);
                    """
                )
                db.execute(
                    """
                    INSERT OR IGNORE INTO conversations
                    (id, user_email, title, archived, created_at, updated_at)
                    SELECT
                        m.conversation_id,
                        m.user_email,
                        COALESCE(
                            NULLIF(SUBSTR((
                                SELECT first_message.content
                                FROM messages first_message
                                WHERE first_message.conversation_id = m.conversation_id
                                  AND first_message.user_email = m.user_email
                                  AND first_message.message_role = 'user'
                                ORDER BY first_message.id
                                LIMIT 1
                            ), 1, 80), ''),
                            'Conversation'
                        ),
                        0,
                        MIN(m.created_at),
                        MAX(m.created_at)
                    FROM messages m
                    GROUP BY m.conversation_id, m.user_email
                    """
                )

    @staticmethod
    def _user(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        result["approved"] = bool(result["approved"])
        result["onboarding_complete"] = bool(result["onboarding_complete"])
        result["profile"] = json.loads(result.pop("profile_json") or "{}")
        return result

    def get_or_create_user(self, email: str, display_name: str) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                db.execute(
                    "UPDATE users SET display_name = ?, updated_at = ? WHERE email = ?",
                    (display_name, now, email),
                )
            else:
                count = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
                role = "owner" if count == 0 else "member"
                approved = 1 if role == "owner" else 0
                db.execute(
                    """
                    INSERT INTO users
                    (email, display_name, role, approved, assigned_team, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'public', ?, ?)
                    """,
                    (email, display_name, role, approved, now, now),
                )
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            db.commit()
        self.audit(email, "user_login", {"mode": settings.app_mode})
        return self._user(row)  # type: ignore[return-value]

    def get_user(self, email: str) -> dict[str, Any] | None:
        with self.connect() as db:
            return self._user(db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())

    def complete_onboarding(
        self,
        email: str,
        *,
        requested_team: str,
        preferred_language: str,
        role_title: str,
        profile: dict[str, Any],
    ) -> dict[str, Any]:
        if requested_team not in TEAMS or requested_team == "public":
            raise ValueError("Select a valid organization department")
        now = utc_now()
        with self.connect() as db:
            current = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
            if current is None:
                raise KeyError("User not found")
            assigned_team = requested_team if current["role"] == "owner" else current["assigned_team"]
            approved = 1 if current["role"] == "owner" else current["approved"]
            db.execute(
                """
                UPDATE users
                SET requested_team = ?, assigned_team = ?, approved = ?,
                    preferred_language = ?, role_title = ?, profile_json = ?,
                    onboarding_complete = 1, updated_at = ?
                WHERE email = ?
                """,
                (
                    requested_team,
                    assigned_team,
                    approved,
                    preferred_language,
                    role_title,
                    json.dumps(profile, ensure_ascii=False),
                    now,
                    email,
                ),
            )
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        self.audit(email, "onboarding_completed", {"requested_team": requested_team})
        return self._user(row)  # type: ignore[return-value]

    def list_users(self) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM users ORDER BY created_at").fetchall()
        return [self._user(row) for row in rows]  # type: ignore[misc]

    def update_language(self, email: str, preferred_language: str) -> dict[str, Any]:
        with self.connect() as db:
            db.execute(
                "UPDATE users SET preferred_language = ?, updated_at = ? WHERE email = ?",
                (preferred_language, utc_now(), email),
            )
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            raise KeyError("User not found")
        self.audit(email, "language_preference_changed", {"language": preferred_language})
        return self._user(row)  # type: ignore[return-value]

    def update_profile(
        self, email: str, *, role_title: str, profile: dict[str, Any]
    ) -> dict[str, Any]:
        now = utc_now()
        with self.connect() as db:
            cursor = db.execute(
                """
                UPDATE users
                SET role_title = ?, profile_json = ?, updated_at = ?
                WHERE email = ?
                """,
                (role_title, json.dumps(profile, ensure_ascii=False), now, email),
            )
            if cursor.rowcount != 1:
                raise KeyError("User not found")
            row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        self.audit(email, "profile_memory_updated", {"fields": sorted(profile)})
        return self._user(row)  # type: ignore[return-value]

    def approve_user(self, actor: str, user_id: int, team: str) -> dict[str, Any]:
        if team not in TEAMS or team == "public":
            raise ValueError("Invalid team")
        with self.connect() as db:
            db.execute(
                "UPDATE users SET assigned_team = ?, approved = 1, updated_at = ? WHERE id = ?",
                (team, utc_now(), user_id),
            )
            row = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise KeyError("User not found")
        self.audit(actor, "user_approved", {"user_id": user_id, "team": team})
        return self._user(row)  # type: ignore[return-value]

    def save_message(
        self,
        conversation_id: str,
        email: str,
        role: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> int:
        now = utc_now()
        title = " ".join(content.strip().split())[:80] or "New conversation"
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO conversations
                (id, user_email, title, archived, created_at, updated_at)
                VALUES (?, ?, ?, 0, ?, ?)
                ON CONFLICT(id, user_email) DO UPDATE SET updated_at = excluded.updated_at
                """,
                (conversation_id, email, title, now, now),
            )
            cursor = db.execute(
                """
                INSERT INTO messages
                (conversation_id, user_email, message_role, content, metadata_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    email,
                    role,
                    content,
                    json.dumps(metadata or {}, ensure_ascii=False),
                    now,
                ),
            )
        return int(cursor.lastrowid)


    def conversation_messages(
        self, conversation_id: str, email: str, limit: int = 6
    ) -> list[dict[str, str]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT message_role, content FROM (
                    SELECT id, message_role, content
                    FROM messages
                    WHERE conversation_id = ? AND user_email = ?
                    ORDER BY id DESC LIMIT ?
                ) ORDER BY id
                """,
                (conversation_id, email, limit),
            ).fetchall()
        return [
            {"role": row["message_role"], "content": row["content"]}
            for row in rows
            if row["message_role"] in {"user", "assistant"}
        ]

    def list_conversations(self, email: str, limit: int = 40) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) AS message_count,
                       COALESCE((
                           SELECT preview.content FROM messages preview
                           WHERE preview.conversation_id = c.id
                             AND preview.user_email = c.user_email
                           ORDER BY preview.id DESC LIMIT 1
                       ), '') AS preview
                FROM conversations c
                LEFT JOIN messages m
                  ON m.conversation_id = c.id AND m.user_email = c.user_email
                WHERE c.user_email = ? AND c.archived = 0
                GROUP BY c.id, c.user_email
                ORDER BY c.updated_at DESC
                LIMIT ?
                """,
                (email, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def conversation_detail(self, conversation_id: str, email: str) -> dict[str, Any]:
        with self.connect() as db:
            conversation = db.execute(
                """
                SELECT id, title, created_at, updated_at
                FROM conversations
                WHERE id = ? AND user_email = ? AND archived = 0
                """,
                (conversation_id, email),
            ).fetchone()
            if conversation is None:
                raise KeyError("Conversation not found")
            rows = db.execute(
                """
                SELECT m.id, m.message_role, m.content, m.metadata_json, m.created_at,
                       f.rating AS feedback_rating
                FROM messages m
                LEFT JOIN message_feedback f
                  ON f.message_id = m.id AND f.user_email = m.user_email
                WHERE m.conversation_id = ? AND m.user_email = ?
                ORDER BY m.id
                """,
                (conversation_id, email),
            ).fetchall()
        messages = []
        for row in rows:
            item = dict(row)
            item["metadata"] = json.loads(item.pop("metadata_json") or "{}")
            messages.append(item)
        return {**dict(conversation), "messages": messages}

    def rename_conversation(self, conversation_id: str, email: str, title: str) -> dict[str, Any]:
        clean_title = " ".join(title.strip().split())[:100]
        if not clean_title:
            raise ValueError("Conversation title is required")
        with self.connect() as db:
            cursor = db.execute(
                """
                UPDATE conversations SET title = ?, updated_at = ?
                WHERE id = ? AND user_email = ? AND archived = 0
                """,
                (clean_title, utc_now(), conversation_id, email),
            )
            if cursor.rowcount != 1:
                raise KeyError("Conversation not found")
        self.audit(email, "conversation_renamed", {"conversation_id": conversation_id})
        return {"id": conversation_id, "title": clean_title}

    def delete_conversation(self, conversation_id: str, email: str) -> None:
        with self.connect() as db:
            exists = db.execute(
                "SELECT 1 FROM conversations WHERE id = ? AND user_email = ?",
                (conversation_id, email),
            ).fetchone()
            if exists is None:
                raise KeyError("Conversation not found")
            message_ids = db.execute(
                "SELECT id FROM messages WHERE conversation_id = ? AND user_email = ?",
                (conversation_id, email),
            ).fetchall()
            if message_ids:
                db.executemany(
                    "DELETE FROM message_feedback WHERE message_id = ? AND user_email = ?",
                    [(row["id"], email) for row in message_ids],
                )
            db.execute(
                "DELETE FROM messages WHERE conversation_id = ? AND user_email = ?",
                (conversation_id, email),
            )
            db.execute(
                "DELETE FROM conversations WHERE id = ? AND user_email = ?",
                (conversation_id, email),
            )
        self.audit(email, "conversation_deleted", {"conversation_id": conversation_id})

    def save_feedback(
        self, message_id: int, email: str, rating: str, comment: str = ""
    ) -> dict[str, Any]:
        if rating not in {"helpful", "not_helpful"}:
            raise ValueError("Rating must be helpful or not_helpful")
        clean_comment = comment.strip()[:1000]
        now = utc_now()
        with self.connect() as db:
            message = db.execute(
                """
                SELECT id, conversation_id FROM messages
                WHERE id = ? AND user_email = ? AND message_role = 'assistant'
                """,
                (message_id, email),
            ).fetchone()
            if message is None:
                raise KeyError("Assistant message not found")
            db.execute(
                """
                INSERT INTO message_feedback
                (message_id, user_email, rating, comment, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(message_id, user_email) DO UPDATE SET
                    rating = excluded.rating,
                    comment = excluded.comment,
                    updated_at = excluded.updated_at
                """,
                (message_id, email, rating, clean_comment, now, now),
            )
        self.audit(
            email,
            "answer_feedback_recorded",
            {"message_id": message_id, "rating": rating},
        )
        return {"message_id": message_id, "rating": rating, "comment": clean_comment}

    def create_action(self, email: str, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        action_id = str(uuid.uuid4())
        now = utc_now()
        with self.connect() as db:
            db.execute(
                """
                INSERT INTO action_requests
                (id, user_email, action_type, payload_json, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'pending_confirmation', ?, ?)
                """,
                (action_id, email, action_type, json.dumps(payload, ensure_ascii=False), now, now),
            )
        self.audit(email, "action_prepared", {"action_id": action_id, "type": action_type})
        return self.get_action(action_id)  # type: ignore[return-value]

    def get_action(self, action_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM action_requests WHERE id = ?", (action_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        result["result"] = json.loads(result.pop("result_json"))
        return result

    def confirm_action(self, email: str, action_id: str) -> dict[str, Any]:
        action = self.get_action(action_id)
        if action is None or action["user_email"] != email:
            raise KeyError("Action not found")
        if action["status"] != "pending_confirmation":
            raise ValueError("Action is no longer pending")
        result = {
            "mode": "sandbox",
            "message": "Action simulated successfully. No external system was changed.",
        }
        with self.connect() as db:
            db.execute(
                """
                UPDATE action_requests
                SET status = 'simulated_completed', result_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (json.dumps(result), utc_now(), action_id),
            )
        self.audit(email, "action_confirmed", {"action_id": action_id, "sandbox": True})
        return self.get_action(action_id)  # type: ignore[return-value]

    def audit(self, email: str | None, event_type: str, details: dict[str, Any]) -> None:
        with self.connect() as db:
            db.execute(
                "INSERT INTO audit_events (user_email, event_type, details_json, created_at) VALUES (?, ?, ?, ?)",
                (email, event_type, json.dumps(details, ensure_ascii=False), utc_now()),
            )

    def recent_audit(self, limit: int = 100) -> list[dict[str, Any]]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT * FROM audit_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            result.append(item)
        return result

    def dashboard_metrics(self) -> dict[str, Any]:
        with self.connect() as db:
            users = db.execute(
                "SELECT COUNT(*) AS total, SUM(approved) AS approved FROM users"
            ).fetchone()
            conversations = db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0]
            messages = db.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN message_role = 'assistant' THEN 1 ELSE 0 END) AS answers
                FROM messages
                """
            ).fetchone()
            feedback_rows = db.execute(
                "SELECT rating, COUNT(*) AS total FROM message_feedback GROUP BY rating"
            ).fetchall()
            pending_actions = db.execute(
                "SELECT COUNT(*) FROM action_requests WHERE status = 'pending_confirmation'"
            ).fetchone()[0]
            metadata_rows = db.execute(
                "SELECT metadata_json FROM messages WHERE message_role = 'assistant'"
            ).fetchall()

        feedback = {row["rating"]: row["total"] for row in feedback_rows}
        feedback_total = sum(feedback.values())
        helpful = feedback.get("helpful", 0)
        latencies = []
        routes: dict[str, int] = {}
        weak_answers = 0
        for row in metadata_rows:
            metadata = json.loads(row["metadata_json"] or "{}")
            route = metadata.get("route")
            if route:
                routes[route] = routes.get(route, 0) + 1
            latency = metadata.get("latency_ms")
            if isinstance(latency, (int, float)):
                latencies.append(float(latency))
            if metadata.get("evidence_status") == "insufficient_evidence":
                weak_answers += 1
        top_routes = [
            {"route": route, "count": count}
            for route, count in sorted(routes.items(), key=lambda item: item[1], reverse=True)[:5]
        ]
        return {
            "users": int(users["total"] or 0),
            "approved_users": int(users["approved"] or 0),
            "conversations": int(conversations or 0),
            "messages": int(messages["total"] or 0),
            "answers": int(messages["answers"] or 0),
            "helpful": int(helpful),
            "not_helpful": int(feedback.get("not_helpful", 0)),
            "helpful_rate": round(helpful * 100 / feedback_total) if feedback_total else None,
            "average_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
            "measured_latency_answers": len(latencies),
            "insufficient_evidence_answers": weak_answers,
            "pending_actions": int(pending_actions or 0),
            "top_routes": top_routes,
        }


control_db = ControlDatabase(settings.control_db_path)
