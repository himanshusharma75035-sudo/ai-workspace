from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
from typing import Any

import httpx

from .config import TEAMS, settings
from .intents import is_broad_organization_overview


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = 1100, overlap: int = 180) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            break_at = max(text.rfind("\n", start + size // 2, end), text.rfind(" ", start + size // 2, end))
            if break_at > start:
                end = break_at
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks




def _document_summary(content: str) -> str:
    first = normalize_text(content).split("\n\n", 1)[0].strip()
    return first.removeprefix("Business model summary:").strip()


def _requested_entities(query: str) -> set[str]:
    excluded = {
        "compare", "company", "draft", "english", "explain", "hinglish",
        "hindi", "please", "prepare", "tell", "what", "which",
    }
    candidates = re.findall(r"\b[A-Z][\w-]{2,}(?:\s+[A-Z][\w-]{2,})?", query)
    return {
        candidate.lower()
        for candidate in candidates
        if candidate.lower() not in excluded
        and candidate.lower() not in settings.organization_aliases
    }

class OllamaEmbedder:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url.rstrip("/")
        self.model = settings.ollama_embedding_model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            with httpx.Client(timeout=180) as client:
                response = client.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": self.model,
                        "input": texts,
                        "truncate": True,
                        "keep_alive": "10m",
                    },
                )
                response.raise_for_status()
            embeddings = response.json().get("embeddings", [])
            return embeddings if len(embeddings) == len(texts) else []
        except Exception:
            return []


def _cosine(left: list[float], right: list[float]) -> float:
    if not left or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


embedding_client = OllamaEmbedder()

def _fts_query(query: str) -> str:
    lowered = query.lower()
    stopwords = {
        "all", "approved", "ask", "automation", "batao", "chhote", "design",
        "does", "email", "explain", "hai", "hinglish", "karo", "karta", "kya",
        "mein", "missing", "monthly", "please", "points", "prepare", "questions",
        "short", "sirf", "samjhao", "sources", "tell", "the", "use", "what",
    }
    tokens = [
        token for token in re.findall(r"[\w]+", lowered, flags=re.UNICODE)
        if len(token) > 1 and token not in stopwords
    ]
    if is_broad_organization_overview(query):
        organization_terms = [
            token
            for alias in settings.organization_aliases
            for token in re.findall(r"[\w]+", alias, flags=re.UNICODE)
        ]
        tokens = [*organization_terms, "business", "model", "overview", "services"]
    tokens = list(dict.fromkeys(tokens))[:12]
    return " OR ".join(f'"{token}"' for token in tokens)


class TeamKnowledgeStore:
    def __init__(self, team: str):
        if team not in TEAMS:
            raise ValueError(f"Unknown team: {team}")
        self.team = team
        self.directory = settings.knowledge_dir / team
        self.path = self.directory / "knowledge.db"

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
                    title,
                    content,
                    source,
                    document_id UNINDEXED,
                    tokenize = 'unicode61 remove_diacritics 2'
                );

                CREATE TABLE IF NOT EXISTS chunk_embeddings (
                    chunk_rowid INTEGER NOT NULL,
                    model TEXT NOT NULL,
                    vector_json TEXT NOT NULL,
                    PRIMARY KEY (chunk_rowid, model)
                );
                """
            )

    def add_document(self, title: str, source: str, content: str) -> dict[str, Any]:
        self.initialize()
        clean = normalize_text(content)
        if not clean:
            raise ValueError("Document contains no readable text")
        digest = hashlib.sha256(clean.encode("utf-8")).hexdigest()
        with self.connect() as db:
            existing = db.execute("SELECT * FROM documents WHERE source = ?", (source,)).fetchone()
            if existing and existing["content_hash"] == digest:
                return {"status": "unchanged", "document_id": existing["id"], "chunks": 0}
            if existing:
                document_id = existing["id"]
                chunk_ids = [
                    row[0] for row in db.execute(
                        "SELECT rowid FROM chunks WHERE document_id = ?", (str(document_id),)
                    ).fetchall()
                ]
                if chunk_ids:
                    db.executemany(
                        "DELETE FROM chunk_embeddings WHERE chunk_rowid = ?",
                        [(chunk_id,) for chunk_id in chunk_ids],
                    )
                db.execute("DELETE FROM chunks WHERE document_id = ?", (str(document_id),))
                db.execute(
                    """
                    UPDATE documents
                    SET title = ?, content_hash = ?, content = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (title, digest, clean, document_id),
                )
            else:
                cursor = db.execute(
                    "INSERT INTO documents (title, source, content_hash, content) VALUES (?, ?, ?, ?)",
                    (title, source, digest, clean),
                )
                document_id = cursor.lastrowid
            chunks = chunk_text(clean)
            db.executemany(
                "INSERT INTO chunks (title, content, source, document_id) VALUES (?, ?, ?, ?)",
                [(title, chunk, source, str(document_id)) for chunk in chunks],
            )
        return {"status": "indexed", "document_id": document_id, "chunks": len(chunks)}

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        self.initialize()
        match = _fts_query(query)
        if not match:
            return []
        try:
            with self.connect() as db:
                rows = db.execute(
                    """
                    SELECT chunks.rowid AS chunk_rowid, chunks.title, chunks.content,
                           chunks.source, chunks.document_id, d.content AS document_content,
                           d.updated_at, bm25(chunks) AS rank
                    FROM chunks
                    JOIN documents d ON d.id = CAST(chunks.document_id AS INTEGER)
                    WHERE chunks MATCH ?
                    ORDER BY rank
                    LIMIT ?
                    """,
                    (match, limit),
                ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [
            {
                "team": self.team,
                "chunk_rowid": int(row["chunk_rowid"]),
                "title": row["title"],
                "content": row["content"],
                "summary": _document_summary(row["document_content"]),
                "source": row["source"],
                "document_id": row["document_id"],
                "updated_at": row["updated_at"],
                "rank": float(row["rank"]),
            }
            for row in rows
        ]

    def rebuild_embeddings(self, *, force: bool = False) -> int:
        self.initialize()
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT chunks.rowid AS chunk_rowid, chunks.title, chunks.content,
                       d.content AS document_content
                FROM chunks
                JOIN documents d ON d.id = CAST(chunks.document_id AS INTEGER)
                ORDER BY chunks.rowid
                """
            ).fetchall()
            existing = {
                row[0] for row in db.execute(
                    "SELECT chunk_rowid FROM chunk_embeddings WHERE model = ?",
                    (embedding_client.model,),
                ).fetchall()
            }
        pending = [row for row in rows if force or row["chunk_rowid"] not in existing]
        if not pending:
            return 0
        vectors = embedding_client.embed(
            [
                f"{row['title']}\n{_document_summary(row['document_content'])}\n{row['content']}"
                for row in pending
            ]
        )
        if len(vectors) != len(pending):
            return 0
        with self.connect() as db:
            db.executemany(
                """
                INSERT OR REPLACE INTO chunk_embeddings
                (chunk_rowid, model, vector_json) VALUES (?, ?, ?)
                """,
                [
                    (row["chunk_rowid"], embedding_client.model, json.dumps(vector))
                    for row, vector in zip(pending, vectors)
                ],
            )
        return len(pending)

    def semantic_search(
        self, query_vector: list[float], limit: int = 10
    ) -> list[dict[str, Any]]:
        if not query_vector:
            return []
        self.initialize()
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT c.rowid AS chunk_rowid, c.title, c.content, c.source,
                       c.document_id, d.content AS document_content, d.updated_at,
                       e.vector_json
                FROM chunks c
                JOIN documents d ON d.id = CAST(c.document_id AS INTEGER)
                JOIN chunk_embeddings e ON e.chunk_rowid = c.rowid
                WHERE e.model = ?
                """,
                (embedding_client.model,),
            ).fetchall()
        results = []
        for row in rows:
            similarity = _cosine(query_vector, json.loads(row["vector_json"]))
            results.append(
                {
                    "team": self.team,
                    "chunk_rowid": int(row["chunk_rowid"]),
                    "title": row["title"],
                    "content": row["content"],
                    "source": row["source"],
                    "document_id": row["document_id"],
                    "updated_at": row["updated_at"],
                    "similarity": similarity,
                }
            )
        results.sort(key=lambda item: item["similarity"], reverse=True)
        return results[:limit]

    def list_documents(self) -> list[dict[str, Any]]:
        self.initialize()
        with self.connect() as db:
            rows = db.execute(
                """
                SELECT d.id, d.title, d.source, d.created_at, d.updated_at,
                       length(d.content) AS characters,
                       (SELECT COUNT(*) FROM chunks c
                        WHERE c.document_id = CAST(d.id AS TEXT)) AS chunk_count,
                       (SELECT COUNT(*) FROM chunk_embeddings e
                        JOIN chunks c ON c.rowid = e.chunk_rowid
                        WHERE c.document_id = CAST(d.id AS TEXT)
                          AND e.model = ?) AS embedded_chunk_count
                FROM documents d ORDER BY d.updated_at DESC
                """
                , (embedding_client.model,)
            ).fetchall()
        return [
            {
                **dict(row),
                "team": self.team,
                "index_status": (
                    "semantic_ready"
                    if row["chunk_count"] and row["embedded_chunk_count"] >= row["chunk_count"]
                    else "keyword_ready"
                ),
            }
            for row in rows
        ]


class KnowledgeManager:
    def initialize(self) -> None:
        settings.knowledge_dir.mkdir(parents=True, exist_ok=True)
        settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        for team in TEAMS:
            TeamKnowledgeStore(team).initialize()
            (settings.uploads_dir / team).mkdir(parents=True, exist_ok=True)

    def add_document(self, team: str, title: str, source: str, content: str) -> dict[str, Any]:
        store = TeamKnowledgeStore(team)
        result = store.add_document(title, source, content)
        result["embedded_chunks"] = store.rebuild_embeddings()
        return result

    def rebuild_embeddings(self, teams: list[str] | None = None, *, force: bool = False) -> dict[str, int]:
        targets = teams or list(TEAMS)
        return {
            team: TeamKnowledgeStore(team).rebuild_embeddings(force=force)
            for team in targets
            if team in TEAMS
        }

    def search(self, query: str, teams: list[str], limit: int = 8) -> list[dict[str, Any]]:
        team_list = [team for team in dict.fromkeys(teams) if team in TEAMS]
        query_vectors = embedding_client.embed([query])
        query_vector = query_vectors[0] if query_vectors else []
        combined: dict[tuple[str, int], dict[str, Any]] = {}

        for team in team_list:
            store = TeamKnowledgeStore(team)
            keyword_results = store.search(query, limit=max(limit * 4, 12))
            semantic_results = store.semantic_search(query_vector, limit=max(limit * 4, 12))
            for position, item in enumerate(keyword_results):
                key = (team, item["chunk_rowid"])
                candidate = combined.setdefault(key, {**item, "retrieval_score": 0.0})
                candidate["retrieval_score"] += 0.35 / (1 + position)
            for item in semantic_results:
                if item["similarity"] < 0.30:
                    continue
                key = (team, item["chunk_rowid"])
                candidate = combined.setdefault(key, {**item, "retrieval_score": 0.0})
                candidate["retrieval_score"] += 0.65 * item["similarity"]

        ranked_all = sorted(
            combined.values(), key=lambda item: item["retrieval_score"], reverse=True
        )
        requested_entities = _requested_entities(query)
        if requested_entities:
            ranked = []
            for entity in sorted(requested_entities):
                matches = [
                    item for item in ranked_all if entity in item["title"].lower()
                ]
                if matches:
                    ranked.append(matches[0])
            ranked.extend(
                item
                for item in ranked_all
                if any(entity in item["title"].lower() for entity in requested_entities)
                and item not in ranked
            )
        else:
            ranked = ranked_all
            if query_vector:
                minimum_score = 0.30 if is_broad_organization_overview(query) else 0.37
                ranked = [item for item in ranked if item["retrieval_score"] >= minimum_score]
        seen: set[str] = set()
        results = []
        for item in ranked:
            key = item["source"]
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
            if len(results) >= limit:
                break
        return results

    def list_documents(self, teams: list[str]) -> list[dict[str, Any]]:
        documents: list[dict[str, Any]] = []
        for team in dict.fromkeys(teams):
            if team in TEAMS:
                documents.extend(TeamKnowledgeStore(team).list_documents())
        return documents


knowledge = KnowledgeManager()
