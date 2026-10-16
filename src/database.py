"""
Database module for LinkedIn Daily Bot.
Handles local SQLite storage (posted.db) for:
- URL deduplication
- Title similarity deduplication
- Topic rotation tracking
- Post logging
"""

import difflib
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from contextlib import contextmanager

logger = logging.getLogger(__name__)


def clean_url(raw_url: str) -> str:
    """Strip tracking query parameters (utm_*, ref, etc.) to standardize URLs."""
    try:
        parsed = urlparse(raw_url)
        params = parse_qs(parsed.query)
        # Drop standard tracking query parameters
        tracking_params = {
            "utm_source", "utm_medium", "utm_campaign", "utm_term",
            "utm_content", "ref", "fbclid", "gclid", "ocid"
        }
        filtered_params = {
            k: v for k, v in params.items() if k.lower() not in tracking_params
        }
        new_query = urlencode(filtered_params, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip("/"),
            parsed.params,
            new_query,
            ""  # drop fragment
        ))
    except Exception:
        return raw_url.strip()


class Database:
    """SQLite database manager for deduplication and post history."""

    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self._init_db()

    @contextmanager
    def _connection(self):
        """Context manager that guarantees connection is closed on exit."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema if it doesn't already exist."""
        with self._connection() as conn:
            cursor = conn.cursor()
            # Posts table: stores all recorded/posted items
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    linkedin_urn TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Index on URL and title for fast lookup
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_url ON posts(url)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_topic ON posts(topic_id)")
            conn.commit()

    def is_url_posted(self, url: str) -> bool:
        """Check if an article URL has already been recorded/posted."""
        normalized = clean_url(url)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM posts WHERE url = ? LIMIT 1", (normalized,))
            return cursor.fetchone() is not None

    def is_similar_title_posted(self, title: str, threshold: float = 0.70, days_lookback: int = 30) -> bool:
        """
        Check if a title is similar to any title posted in the lookback window.
        Uses difflib.SequenceMatcher to calculate similarity ratio (0.0 to 1.0).
        """
        title_lower = title.strip().lower()
        cutoff_date = (datetime.utcnow() - timedelta(days=days_lookback)).strftime("%Y-%m-%d %H:%M:%S")

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT title FROM posts WHERE created_at >= ?",
                (cutoff_date,)
            )
            rows = cursor.fetchall()

        for row in rows:
            existing_title = row["title"].strip().lower()
            similarity = difflib.SequenceMatcher(None, title_lower, existing_title).ratio()
            if similarity >= threshold:
                logger.debug(
                    f"Title '{title}' is similar ({similarity:.2f} >= {threshold}) to existing: '{row['title']}'"
                )
                return True

        return False

    def get_last_posted_topic(self) -> Optional[str]:
        """Return the topic_id of the most recent successfully posted item."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT topic_id FROM posts WHERE status = 'posted' ORDER BY id DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if row:
                return row["topic_id"]
        return None

    def get_topic_counts(self, days_lookback: int = 14) -> Dict[str, int]:
        """Return a tally of how many times each topic was posted recently."""
        cutoff_date = (datetime.utcnow() - timedelta(days=days_lookback)).strftime("%Y-%m-%d %H:%M:%S")
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT topic_id, COUNT(*) as count
                FROM posts
                WHERE status = 'posted' AND created_at >= ?
                GROUP BY topic_id
                """,
                (cutoff_date,)
            )
            return {row["topic_id"]: row["count"] for row in cursor.fetchall()}

    def record_post(
        self,
        topic_id: str,
        title: str,
        url: str,
        content: str,
        status: str = "posted",
        linkedin_urn: Optional[str] = None
    ) -> int:
        """
        Record a post in the database.
        Returns the inserted row ID.
        """
        normalized_url = clean_url(url)
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO posts (topic_id, title, url, content, status, linkedin_urn, created_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """,
                (topic_id, title.strip(), normalized_url, content.strip(), status, linkedin_urn)
            )
            conn.commit()
            return cursor.lastrowid

    def get_recent_posts(self, limit: int = 10) -> List[dict]:
        """Retrieve the most recent posts."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, topic_id, title, url, content, status, linkedin_urn, created_at
                FROM posts
                ORDER BY id DESC LIMIT ?
                """,
                (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]
