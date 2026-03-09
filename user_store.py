import json
import os
import threading

DATA_FILE = "user_data.json"

_lock = threading.Lock()
_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is not None:
        return _cache
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                _cache = json.load(f)
                return _cache
        except (json.JSONDecodeError, OSError) as e:
            print(f"[user_store] 데이터 파일 읽기 오류: {e}")
    _cache = {}
    return _cache


def _save(data: dict):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_dorm(user_id: str | None) -> str | None:
    if not user_id:
        return None
    with _lock:
        return _load().get(user_id)


def set_user_dorm(user_id: str | None, dorm: str):
    if not user_id:
        return
    with _lock:
        data = _load()
        data[user_id] = dorm
        _save(data)
