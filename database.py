import sqlite3
from datetime import datetime, date


class Database:
    def __init__(self, path: str = "bot.db"):
        self.conn = sqlite3.connect(path)
        self._init()

    def _init(self):
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_posts (
                post_id TEXT PRIMARY KEY,
                replied INTEGER,
                created_at TEXT
            )
        """)
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_posts (
                post_date TEXT PRIMARY KEY,
                created_at TEXT
            )
        """)
        self.conn.commit()

    def already_processed(self, post_id: str) -> bool:
        row = self.conn.execute(
            "SELECT replied FROM processed_posts WHERE post_id = ?", (post_id,)
        ).fetchone()
        return row is not None

    def mark_replied(self, post_id: str):
        self.conn.execute(
            "INSERT OR REPLACE INTO processed_posts (post_id, replied, created_at) VALUES (?, 1, ?)",
            (post_id, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def mark_skipped(self, post_id: str):
        self.conn.execute(
            "INSERT OR IGNORE INTO processed_posts (post_id, replied, created_at) VALUES (?, 0, ?)",
            (post_id, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def posted_today(self) -> bool:
        today = date.today().isoformat()
        row = self.conn.execute(
            "SELECT 1 FROM daily_posts WHERE post_date = ?", (today,)
        ).fetchone()
        return row is not None

    def mark_daily_post(self):
        today = date.today().isoformat()
        self.conn.execute(
            "INSERT OR IGNORE INTO daily_posts (post_date, created_at) VALUES (?, ?)",
            (today, datetime.utcnow().isoformat()),
        )
        self.conn.commit()

    def close(self):
        self.conn.close()
