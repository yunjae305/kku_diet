import os
from flask import Flask, request, jsonify
from crawler import get_today_meals, get_tomorrow_meals, get_week_meals
from user_store import get_user_dorm, set_user_dorm

DORM_NAMES = {"haeoreum": "해오름학사", "mosirae": "모시래학사"}

app = Flask(__name__)
app.json.ensure_ascii = False


def _get_user_info():
    body = request.get_json(silent=True) or {}
    user_request = body.get("userRequest", {})
    user_id = user_request.get("user", {}).get("id")
    utterance = user_request.get("utterance", "")
    return user_id, utterance


def _make_response(text, quick_replies=None):
    res = {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": text}}]}}
    if quick_replies:
        res["template"]["quickReplies"] = quick_replies
    return jsonify(res)


def _make_carousel_response(cards):
    res = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "carousel": {
                        "type": "basicCard",
                        "items": cards,
                    }
                }
            ]
        },
    }
    return jsonify(res)


@app.route('/api/register/haeoreum', methods=['POST'])
def register_haeoreum():
    user_id, _ = _get_user_info()
    if not user_id:
        return _make_response("사용자 정보를 확인할 수 없습니다.")
    set_user_dorm(user_id, "haeoreum")
    return _make_response("해오름학사 등록 완료!\n이제 '오늘학식'을 입력해보세요.")


@app.route('/api/register/mosirae', methods=['POST'])
def register_mosirae():
    user_id, _ = _get_user_info()
    if not user_id:
        return _make_response("사용자 정보를 확인할 수 없습니다.")
    set_user_dorm(user_id, "mosirae")
    return _make_response("모시래학사 등록 완료!\n이제 '오늘학식'을 입력해보세요.")


@app.route('/api/diet', methods=['POST'])
def diet_api():
    user_id, utterance = _get_user_info()
    dorm = get_user_dorm(user_id)

    if not dorm:
        return _make_response("기숙사 등록이 필요합니다.", [
            {"label": "해오름학사 등록", "action": "message", "messageText": "해오름학사 등록"},
            {"label": "모시래학사 등록", "action": "message", "messageText": "모시래학사 등록"}
        ])

    if "내일" in utterance:
        result = get_tomorrow_meals(dorm=dorm)
    else:
        result = get_today_meals(dorm=dorm)
    return _make_response(result)


_NO_DORM_REPLIES = [
    {"label": "해오름학사 등록", "action": "message", "messageText": "해오름학사 등록"},
    {"label": "모시래학사 등록", "action": "message", "messageText": "모시래학사 등록"},
]


@app.route('/api/weekly', methods=['POST'])
def weekly_api():
    user_id, _ = _get_user_info()
    dorm = get_user_dorm(user_id)
    if not dorm:
        return _make_response("기숙사 등록이 필요합니다.", _NO_DORM_REPLIES)
    cards = get_week_meals(dorm=dorm)
    if isinstance(cards, str):
        return _make_response(cards)
    return _make_carousel_response(cards)


@app.route('/api/myinfo', methods=['POST'])
def myinfo_api():
    user_id, _ = _get_user_info()
    dorm = get_user_dorm(user_id)
    if not dorm:
        return _make_response("기숙사 등록이 필요합니다.", _NO_DORM_REPLIES)
    dorm_name = DORM_NAMES.get(dorm, dorm)
    return _make_response(f"⚙️ 현재 설정\n• 기숙사: {dorm_name}")


@app.route('/api/settings', methods=['POST'])
def settings_api():
    user_id, _ = _get_user_info()
    dorm = get_user_dorm(user_id)
    dorm_name = DORM_NAMES.get(dorm, "미등록") if dorm else "미등록"
    return _make_response(
        f"⚙️ 현재 설정\n• 기숙사: {dorm_name}\n\n변경하실 항목을 선택해주세요.",
        [
            {"label": "🏠 모시래학사", "action": "message", "messageText": "모시래학사 등록"},
            {"label": "🏠 해오름학사", "action": "message", "messageText": "해오름학사 등록"},
        ]
    )


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
