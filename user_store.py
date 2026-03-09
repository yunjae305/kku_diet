import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "users.db")


def _get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id    TEXT PRIMARY KEY,
            dorm       TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    return conn


def get_user_dorm(user_id):
    if not user_id:
        return None
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT dorm FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row[0] if row else None


def set_user_dorm(user_id, dorm):
    if not user_id:
        return
    with _get_conn() as conn:
        conn.execute(
            "INSERT INTO users (user_id, dorm) VALUES (?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET dorm=excluded.dorm, updated_at=CURRENT_TIMESTAMP",
            (user_id, dorm),
        )
        conn.commit()
