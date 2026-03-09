import os
from flask import Flask, request, jsonify, Response
from crawler import get_today_meals, get_tomorrow_meals, get_week_data
from user_store import get_user_dorm, set_user_dorm
from image_gen import generate_weekly_image

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


def _make_image_response(image_url):
    res = {
        "version": "2.0",
        "template": {
            "outputs": [
                {
                    "simpleImage": {
                        "imageUrl": image_url,
                        "altText": "이번주 식단표",
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

    # 이미지 URL 구성 (https 강제)
    base_url = request.host_url.replace("http://", "https://")
    image_url = f"{base_url}api/weekly_image?dorm={dorm}"
    return _make_image_response(image_url)


@app.route('/api/weekly_image', methods=['GET'])
def weekly_image():
    dorm = request.args.get("dorm", "haeoreum")
    result = get_week_data(dorm)
    if isinstance(result, str):
        return result, 500
    config, monday, meals = result
    try:
        png_bytes = generate_weekly_image(config, monday, meals)
        return Response(png_bytes, mimetype="image/png")
    except Exception as e:
        print(f"[image_gen] 오류: {e}")
        return "이미지 생성 오류", 500


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


# ── Cloud Functions 진입점 ──────────────────────────────────────
try:
    import functions_framework

    @functions_framework.http
    def kku_diet(request):
        with app.test_request_context(
            path=request.path,
            method=request.method,
            data=request.get_data(),
            content_type=request.content_type,
            headers=dict(request.headers),
            query_string=request.query_string,
        ):
            return app.full_dispatch_request()

except ImportError:
    pass  # 로컬 실행 시 무시


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
