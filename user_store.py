import sqlite3
import json
import os

DB_FILE = "users.db"
_LEGACY_JSON = "user_data.json"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db():
    with _get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id   TEXT PRIMARY KEY,
                dorm      TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

    # 기존 JSON 데이터 자동 마이그레이션
    if os.path.exists(_LEGACY_JSON):
        try:
            with open(_LEGACY_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            with _get_conn() as conn:
                conn.executemany(
                    "INSERT OR IGNORE INTO users (user_id, dorm) VALUES (?, ?)",
                    data.items(),
                )
                conn.commit()
            os.rename(_LEGACY_JSON, _LEGACY_JSON + ".migrated")
            print(f"[user_store] JSON → SQLite 마이그레이션 완료: {len(data)}명")
        except Exception as e:
            print(f"[user_store] 마이그레이션 오류: {e}")


_init_db()


def get_user_dorm(user_id: str | None) -> str | None:
    if not user_id:
        return None
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT dorm FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
    return row["dorm"] if row else None


def set_user_dorm(user_id: str | None, dorm: str):
    if not user_id:
        return
    with _get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO users (user_id, dorm, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
            (user_id, dorm),
        )
        conn.commit()
