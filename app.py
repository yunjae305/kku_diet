"""
건국대학교 글로컬캠퍼스 기숙사 식단 챗봇 서버
카카오톡 스킬 서버 (Flask)
해오름학사 + 모시래학사 지원 + 사용자별 기숙사 설정
"""

from flask import Flask, request, jsonify
from crawler import (
    get_diet, get_today_meals, get_tomorrow_meals,
    get_haeoreum_today, get_haeoreum_tomorrow,
    get_mosirae_today, get_mosirae_tomorrow
)
from user_store import (
    get_user_dorm, set_user_dorm, is_user_registered, get_dorm_name, delete_user
)

app = Flask(__name__)
app.json.ensure_ascii = False


# === 헬퍼 함수 ===

def make_simple_text_response(text: str) -> dict:
    """카카오톡 SimpleText 응답"""
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": text}}
            ]
        }
    }


def make_quick_reply_response(text: str, quick_replies: list) -> dict:
    """카카오톡 QuickReplies 응답 (버튼 선택)"""
    return {
        "version": "2.0",
        "template": {
            "outputs": [
                {"simpleText": {"text": text}}
            ],
            "quickReplies": quick_replies
        }
    }


def make_dorm_selection_response() -> dict:
    """기숙사 선택 QuickReplies"""
    return make_quick_reply_response(
        "어떤 기숙사에 거주하시나요?",
        [
            {
                "label": "해오름학사",
                "action": "message",
                "messageText": "해오름학사 등록"
            },
            {
                "label": "모시래학사",
                "action": "message",
                "messageText": "모시래학사 등록"
            }
        ]
    )


def extract_user_id(body: dict) -> str:
    """카카오톡 요청에서 사용자 ID 추출"""
    try:
        return body.get("userRequest", {}).get("user", {}).get("id", "")
    except (AttributeError, TypeError):
        return ""


def extract_utterance(body: dict) -> str:
    """카카오톡 요청에서 발화 추출"""
    try:
        return body.get("userRequest", {}).get("utterance", "")
    except (AttributeError, TypeError):
        return ""


def extract_params(body: dict) -> dict:
    """카카오톡 요청에서 파라미터 추출"""
    try:
        return body.get("action", {}).get("params", {})
    except (AttributeError, TypeError):
        return {}


# ============================================================
# 사용자 등록/설정 API
# ============================================================

@app.route('/api/register', methods=['POST'])
def register_api():
    """
    사용자 등록 시작 - 기숙사 선택 버튼 표시
    발화: "등록", "시작", "설정"
    """
    return jsonify(make_dorm_selection_response())


@app.route('/api/register/haeoreum', methods=['POST'])
def register_haeoreum_api():
    """해오름학사로 등록"""
    body = request.get_json(silent=True) or {}
    user_id = extract_user_id(body)

    if not user_id:
        return jsonify(make_simple_text_response("사용자 정보를 확인할 수 없습니다."))

    set_user_dorm(user_id, "haeoreum")
    return jsonify(make_simple_text_response(
        "해오름학사로 등록되었습니다!\n\n"
        "이제 '오늘 학식' 또는 '내일 학식'이라고 말씀해주세요."
    ))


@app.route('/api/register/mosirae', methods=['POST'])
def register_mosirae_api():
    """모시래학사로 등록"""
    body = request.get_json(silent=True) or {}
    user_id = extract_user_id(body)

    if not user_id:
        return jsonify(make_simple_text_response("사용자 정보를 확인할 수 없습니다."))

    set_user_dorm(user_id, "mosirae")
    return jsonify(make_simple_text_response(
        "모시래학사로 등록되었습니다!\n\n"
        "이제 '오늘 학식' 또는 '내일 학식'이라고 말씀해주세요."
    ))


@app.route('/api/myinfo', methods=['POST'])
def myinfo_api():
    """내 정보 조회"""
    body = request.get_json(silent=True) or {}
    user_id = extract_user_id(body)

    if not user_id:
        return jsonify(make_simple_text_response("사용자 정보를 확인할 수 없습니다."))

    dorm = get_user_dorm(user_id)
    if dorm:
        dorm_name = get_dorm_name(dorm)
        return jsonify(make_simple_text_response(
            f"[ 내 정보 ]\n"
            f"등록된 기숙사: {dorm_name}\n\n"
            f"기숙사를 변경하려면 '기숙사 변경'이라고 말씀해주세요."
        ))
    else:
        return jsonify(make_dorm_selection_response())


@app.route('/api/change', methods=['POST'])
def change_dorm_api():
    """기숙사 변경 - 선택 버튼 표시"""
    return jsonify(make_dorm_selection_response())


# ============================================================
# 사용자 맞춤 식단 API (등록된 기숙사 기반)
# ============================================================

@app.route('/api/diet', methods=['GET', 'POST'])
def diet_api():
    """
    오늘 식단 조회 (사용자 등록 기숙사 기반)
    미등록 사용자는 기숙사 선택 안내
    """
    body = request.get_json(silent=True) or {}
    user_id = extract_user_id(body)

    # 사용자 기숙사 확인
    dorm = get_user_dorm(user_id)

    if not dorm:
        # 미등록 사용자 -> 기숙사 선택 안내
        return jsonify(make_dorm_selection_response())

    # 등록된 기숙사의 오늘 식단
    result = get_today_meals(dorm=dorm)
    return jsonify(make_simple_text_response(result))


@app.route('/api/diet/tomorrow', methods=['GET', 'POST'])
def diet_tomorrow_api():
    """
    내일 식단 조회 (사용자 등록 기숙사 기반)
    """
    body = request.get_json(silent=True) or {}
    user_id = extract_user_id(body)

    dorm = get_user_dorm(user_id)

    if not dorm:
        return jsonify(make_dorm_selection_response())

    result = get_tomorrow_meals(dorm=dorm)
    return jsonify(make_simple_text_response(result))


# ============================================================
# 특정 기숙사 직접 조회 API (등록 무관)
# ============================================================

@app.route('/api/haeoreum', methods=['GET', 'POST'])
def haeoreum_today_api():
    """해오름학사 오늘 식단"""
    result = get_haeoreum_today()
    return jsonify(make_simple_text_response(result))


@app.route('/api/haeoreum/tomorrow', methods=['GET', 'POST'])
def haeoreum_tomorrow_api():
    """해오름학사 내일 식단"""
    result = get_haeoreum_tomorrow()
    return jsonify(make_simple_text_response(result))


@app.route('/api/mosirae', methods=['GET', 'POST'])
def mosirae_today_api():
    """모시래학사 오늘 식단"""
    result = get_mosirae_today()
    return jsonify(make_simple_text_response(result))


@app.route('/api/mosirae/tomorrow', methods=['GET', 'POST'])
def mosirae_tomorrow_api():
    """모시래학사 내일 식단"""
    result = get_mosirae_tomorrow()
    return jsonify(make_simple_text_response(result))


# ============================================================
# 상태 확인용
# ============================================================

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "KKU 기숙사 식단봇 정상 작동 중"})


@app.route('/', methods=['GET'])
def index():
    return jsonify({
        "name": "KKU 기숙사 식단 챗봇",
        "version": "2.1.0",
        "features": ["사용자별 기숙사 등록", "해오름학사", "모시래학사"],
        "endpoints": {
            "사용자 등록": {
                "/api/register": "기숙사 선택 시작",
                "/api/register/haeoreum": "해오름학사 등록",
                "/api/register/mosirae": "모시래학사 등록",
                "/api/myinfo": "내 정보 조회",
                "/api/change": "기숙사 변경"
            },
            "식단 조회 (사용자 맞춤)": {
                "/api/diet": "오늘 식단",
                "/api/diet/tomorrow": "내일 식단"
            },
            "직접 조회": {
                "/api/haeoreum": "해오름 오늘",
                "/api/haeoreum/tomorrow": "해오름 내일",
                "/api/mosirae": "모시래 오늘",
                "/api/mosirae/tomorrow": "모시래 내일"
            }
        }
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
