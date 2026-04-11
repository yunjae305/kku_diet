import os
import json
import hashlib
import uuid
import time
from dotenv import load_dotenv
load_dotenv()
from flask import Flask, request, jsonify, Response
from crawler import get_today_meals, get_tomorrow_meals, get_week_data
from user_store import get_user_dorm, set_user_dorm

DORM_NAMES = {"haeoreum": "해오름학사", "mosirae": "모시래학사"}

app = Flask(__name__)
app.json.ensure_ascii = False

# 미리 생성된 이미지를 임시 저장하는 캐시: {key: (생성시각, png_bytes)}
# 카카오가 이미지 URL을 fetch할 때 즉시 반환하기 위해 사용
_img_cache: dict = {}
_weekly_image_cache: dict = {}
_IMG_CACHE_TTL = 300  # 5분


def _cleanup_img_cache(now_ts):
    expired_image_keys = [k for k, (ts, _) in _img_cache.items() if now_ts - ts > _IMG_CACHE_TTL]
    for cache_key in expired_image_keys:
        del _img_cache[cache_key]

    expired_weekly_keys = [k for k, (ts, _) in _weekly_image_cache.items() if now_ts - ts > _IMG_CACHE_TTL]
    for payload_key in expired_weekly_keys:
        del _weekly_image_cache[payload_key]


def _build_weekly_payload_key(dorm, monday, meals):
    meals_json = json.dumps(meals, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha1(meals_json.encode("utf-8")).hexdigest()
    return f"{dorm}:{monday.strftime('%Y-%m-%d')}:{digest}"


def _get_user_info():
    """카카오 요청 바디에서 사용자 ID와 발화를 추출합니다."""
    body = request.get_json(silent=True) or {}
    user_request = body.get("userRequest", {})
    user_id = user_request.get("user", {}).get("id")
    utterance = user_request.get("utterance", "")
    return user_id, utterance


def _make_response(text, quick_replies=None):
    """카카오 simpleText 응답을 생성합니다."""
    res = {"version": "2.0", "template": {"outputs": [{"simpleText": {"text": text}}]}}
    if quick_replies:
        res["template"]["quickReplies"] = quick_replies
    return jsonify(res)


def _make_image_response(image_url):
    """카카오 simpleImage 응답을 생성합니다."""
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


# 기숙사 미등록 시 표시할 빠른답변 버튼
_NO_DORM_REPLIES = [
    {"label": "해오름학사 등록", "action": "message", "messageText": "해오름학사 등록"},
    {"label": "모시래학사 등록", "action": "message", "messageText": "모시래학사 등록"},
]


@app.route('/api/register/haeoreum', methods=['POST'])
def register_haeoreum():
    """해오름학사 등록"""
    user_id, _ = _get_user_info()
    if not user_id:
        return _make_response("사용자 정보를 확인할 수 없습니다.")
    set_user_dorm(user_id, "haeoreum")
    return _make_response("해오름학사 등록 완료!\n이제 '오늘학식'을 입력해보세요.")


@app.route('/api/register/mosirae', methods=['POST'])
def register_mosirae():
    """모시래학사 등록"""
    user_id, _ = _get_user_info()
    if not user_id:
        return _make_response("사용자 정보를 확인할 수 없습니다.")
    set_user_dorm(user_id, "mosirae")
    return _make_response("모시래학사 등록 완료!\n이제 '오늘학식'을 입력해보세요.")


@app.route('/api/diet', methods=['POST'])
def diet_api():
    """오늘 또는 내일 식단 조회. 발화에 '내일' 포함 시 내일 식단 반환."""
    user_id, utterance = _get_user_info()
    dorm = get_user_dorm(user_id)

    if not dorm:
        return _make_response("기숙사 등록이 필요합니다.", _NO_DORM_REPLIES)

    if "내일" in utterance:
        result = get_tomorrow_meals(dorm=dorm)
    else:
        result = get_today_meals(dorm=dorm)
    return _make_response(result)


@app.route('/api/weekly', methods=['POST'])
def weekly_api():
    """이번 주 식단 이미지를 생성하여 캐싱 후 URL을 반환합니다.

    카카오가 이미지 URL을 fetch할 때 즉시 응답할 수 있도록,
    이 엔드포인트에서 미리 이미지를 생성하고 메모리에 저장합니다.
    """
    user_id, _ = _get_user_info()
    dorm = get_user_dorm(user_id)
    if not dorm:
        return _make_response("기숙사 등록이 필요합니다.", _NO_DORM_REPLIES)

    # 식단 데이터 크롤링
    result = get_week_data(dorm)
    if isinstance(result, str):
        return _make_response(result)

    config, monday, meals = result

    now = time.time()
    _cleanup_img_cache(now)
    payload_key = _build_weekly_payload_key(dorm, monday, meals)
    cached_entry = _weekly_image_cache.get(payload_key)
    if cached_entry:
        _, cached_key = cached_entry
        cached_image = _img_cache.get(cached_key)
        if cached_image:
            _img_cache[cached_key] = (now, cached_image[1])
            _weekly_image_cache[payload_key] = (now, cached_key)
            base_url = request.host_url.replace("http://", "https://")
            image_url = f"{base_url}api/weekly_image/{cached_key}"
            return _make_image_response(image_url)

    # 이미지 생성 후 메모리 캐시에 저장
    try:
        from image_gen import generate_weekly_image
        png_bytes = generate_weekly_image(config, monday, meals)
    except Exception as e:
        print(f"[weekly_api] 이미지 생성 오류: {e}")
        return _make_response("이미지 생성 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

    key = uuid.uuid4().hex
    _img_cache[key] = (now, png_bytes)
    _weekly_image_cache[payload_key] = (now, key)

    # 카카오에 이미지 URL 반환 (https 강제)
    base_url = request.host_url.replace("http://", "https://")
    image_url = f"{base_url}api/weekly_image/{key}"
    return _make_image_response(image_url)


@app.route('/api/weekly_image/<key>', methods=['GET'])
def weekly_image(key):
    """미리 생성된 주간 식단 이미지를 반환합니다. (카카오 서버가 호출)"""
    now = time.time()
    _cleanup_img_cache(now)
    entry = _img_cache.get(key)
    if not entry:
        return "이미지를 찾을 수 없습니다. 다시 시도해주세요.", 404

    _, png_bytes = entry
    _img_cache[key] = (now, png_bytes)
    return Response(png_bytes, mimetype="image/png")


@app.route('/api/myinfo', methods=['POST'])
def myinfo_api():
    """현재 등록된 기숙사 정보를 반환합니다."""
    user_id, _ = _get_user_info()
    dorm = get_user_dorm(user_id)
    if not dorm:
        return _make_response("기숙사 등록이 필요합니다.", _NO_DORM_REPLIES)
    dorm_name = DORM_NAMES.get(dorm, dorm)
    return _make_response(f"⚙️ 현재 설정\n• 기숙사: {dorm_name}")


@app.route('/api/settings', methods=['POST'])
def settings_api():
    """기숙사 설정 확인 및 변경 버튼을 제공합니다."""
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


@app.route('/health')
def health_check():
    """Render 헬스체크 및 슬립 방지용 엔드포인트"""
    return "OK", 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
