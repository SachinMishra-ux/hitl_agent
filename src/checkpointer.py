import os
import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from langgraph.checkpoint.sqlite import SqliteSaver
from src.config import settings

logger = logging.getLogger(__name__)

_checkpointer_instance: Optional[SqliteSaver] = None
_db_conn: Optional[sqlite3.Connection] = None


def get_db_connection() -> sqlite3.Connection:
    global _db_conn
    if _db_conn is None:
        os.makedirs(os.path.dirname(settings.SQLITE_DB_PATH), exist_ok=True)
        _db_conn = sqlite3.connect(settings.SQLITE_DB_PATH, check_same_thread=False)
        _db_conn.row_factory = sqlite3.Row
        init_metadata_table(_db_conn)
    return _db_conn


def init_metadata_table(conn: sqlite3.Connection):
    """
    Initializes metadata table to easily index and query HITL threads and their statuses.
    """
    with conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS post_metadata (
                thread_id TEXT PRIMARY KEY,
                topic TEXT,
                status TEXT,
                current_draft TEXT,
                post_id TEXT,
                post_url TEXT,
                error TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )


def get_checkpointer() -> SqliteSaver:
    """
    Returns singleton SqliteSaver checkpointer for LangGraph persistent workflows.
    """
    global _checkpointer_instance
    if _checkpointer_instance is None:
        conn = get_db_connection()
        _checkpointer_instance = SqliteSaver(conn)
        _checkpointer_instance.setup()
        logger.info(f"SqliteSaver initialized at: {settings.SQLITE_DB_PATH}")
    return _checkpointer_instance


def save_post_metadata(
    thread_id: str,
    topic: str,
    status: str,
    draft: str,
    post_id: Optional[str] = None,
    post_url: Optional[str] = None,
    error: Optional[str] = None,
):
    conn = get_db_connection()
    now = datetime.now().isoformat()
    with conn:
        conn.execute(
            """
            INSERT INTO post_metadata (thread_id, topic, status, current_draft, post_id, post_url, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(thread_id) DO UPDATE SET
                status = excluded.status,
                current_draft = excluded.current_draft,
                post_id = COALESCE(excluded.post_id, post_metadata.post_id),
                post_url = COALESCE(excluded.post_url, post_metadata.post_url),
                error = excluded.error,
                updated_at = excluded.updated_at
            """,
            (thread_id, topic, status, draft, post_id, post_url, error, now, now),
        )


def get_all_posts_metadata() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM post_metadata ORDER BY updated_at DESC")
    rows = cursor.fetchall()
    return [dict(row) for row in rows]


def get_post_metadata(thread_id: str) -> Optional[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM post_metadata WHERE thread_id = ?", (thread_id,))
    row = cursor.fetchone()
    return dict(row) if row else None
