"""
사용자 정보 저장소
JSON 파일 기반 간단한 저장소
"""

import json
import os
from typing import Optional

# 사용자 데이터 파일 경로
DATA_FILE = os.path.join(os.path.dirname(__file__), "user_data.json")


def _load_data() -> dict:
    """JSON 파일에서 데이터 로드"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_data(data: dict) -> None:
    """JSON 파일에 데이터 저장"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_user_dorm(user_id: str) -> Optional[str]:
    """
    사용자의 기숙사 설정 조회

    Returns:
        "haeoreum", "mosirae", 또는 None (미등록)
    """
    if not user_id:
        return None

    data = _load_data()
    user_info = data.get(user_id, {})
    return user_info.get("dorm")


def set_user_dorm(user_id: str, dorm: str) -> bool:
    """
    사용자의 기숙사 설정 저장

    Args:
        user_id: 카카오톡 사용자 ID
        dorm: "haeoreum" 또는 "mosirae"

    Returns:
        성공 여부
    """
    if not user_id or dorm not in ("haeoreum", "mosirae"):
        return False

    data = _load_data()

    if user_id not in data:
        data[user_id] = {}

    data[user_id]["dorm"] = dorm
    _save_data(data)
    return True


def is_user_registered(user_id: str) -> bool:
    """사용자 등록 여부 확인"""
    return get_user_dorm(user_id) is not None


def get_dorm_name(dorm: str) -> str:
    """기숙사 코드를 한글 이름으로 변환"""
    names = {
        "haeoreum": "해오름학사",
        "mosirae": "모시래학사"
    }
    return names.get(dorm, "알 수 없음")


def delete_user(user_id: str) -> bool:
    """사용자 정보 삭제"""
    if not user_id:
        return False

    data = _load_data()
    if user_id in data:
        del data[user_id]
        _save_data(data)
        return True
    return False
