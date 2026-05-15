import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta, timezone

requests.packages.urllib3.disable_warnings()

KST = timezone(timedelta(hours=9))
import time

BASE_URL = "https://dorm.kku.ac.kr"

# 기숙사별 설정 (이름, 세션 파라미터, 식사 종류)
DORM_CONFIG = {
    "haeoreum": {
        "name": "해오름학사",
        "dorm_type": "H",
        "params": {"menuSeq": "43885", "bachelor": "HA"},
        "meals": ["점심", "저녁"],
        "meal_times": {"점심": "11:30 ~ 13:30", "저녁": "17:30 ~ 19:00"},
        "has_weekend": False,
    },
    "mosirae": {
        "name": "모시래학사",
        "dorm_type": "M",
        "params": {"menuSeq": "43860", "bachelor": "MO"},
        "meals": ["아침", "점심", "저녁"],
        "meal_times": {
            "weekday": {"아침": "08:00 ~ 09:00", "점심": "12:00 ~ 13:30", "저녁": "16:50 ~ 18:30"},
            "weekend": {"아침": "08:30 ~ 09:30", "점심": "12:00 ~ 13:00", "저녁": "17:00 ~ 18:00"},
        },
        "has_weekend": True,
    },
}

_MEAL_EMOJI = {"아침": "🌅", "점심": "🍴", "저녁": "🌙"}


def _meal_label(config, meal, weekday):
    meal_times = config.get("meal_times", {})
    if "weekday" in meal_times or "weekend" in meal_times:
        day_type = "weekend" if weekday > 4 else "weekday"
        meal_times = meal_times.get(day_type, {})
    if meal in meal_times:
        return f"{meal}({meal_times[meal]})"
    return meal

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# TTL 캐시: key -> (저장 시각, 데이터)
_cache: dict = {}
_CACHE_TTL = 600  # 10분


_CACHE_SWEEP_INTERVAL = 300
_last_cache_sweep_at = 0.0
_REQUEST_TIMEOUT = float(os.environ.get("CRAWLER_TIMEOUT_SEC", "10"))


def _sweep_expired_cache(now):
    global _last_cache_sweep_at
    if now - _last_cache_sweep_at < _CACHE_SWEEP_INTERVAL:
        return
    _last_cache_sweep_at = now

    expired = [k for k, (ts, _) in _cache.items() if now - ts >= _CACHE_TTL]
    for cache_key in expired:
        del _cache[cache_key]


def _set_cached(key, value):
    now = time.time()
    _sweep_expired_cache(now)
    _cache[key] = (now, value)


def _get_cached(key):
    """캐시에서 유효한 데이터를 반환합니다. 만료된 경우 삭제 후 None 반환."""
    now = time.time()
    _sweep_expired_cache(now)
    if key in _cache:
        ts, value = _cache[key]
        if now - ts < _CACHE_TTL:
            return value
        del _cache[key]
    return None


def _fetch_diet_html(config: dict) -> str:
    """3단계 세션 흐름으로 식단 페이지 HTML을 가져옵니다.

    기숙사 홈페이지는 세션 없이 접근하면 landing.do로 리다이렉트됩니다.
    ① GET /landing.do        → JSESSIONID 쿠키 획득
    ② GET /main.do?dormType= → 기숙사 컨텍스트 세션 설정
    ③ GET /weekly_diet.do    → 식단 HTML 파싱
    """
    session = requests.Session()
    session.verify = False
    session.headers.update(_HEADERS)
    dorm_type = config["dorm_type"]

    session.get(f"{BASE_URL}/landing.do", timeout=_REQUEST_TIMEOUT)

    main_url = f"{BASE_URL}/main.do?dormType={dorm_type}"
    session.get(main_url, headers={"Referer": f"{BASE_URL}/landing.do"}, timeout=_REQUEST_TIMEOUT)

    diet_url = f"{BASE_URL}/weekly_diet.do"
    response = session.get(
        diet_url,
        params=config["params"],
        headers={"Referer": main_url},
        timeout=_REQUEST_TIMEOUT,
    )
    response.encoding = "utf-8"
    return response.text


def _parse_meals(rows, meal_types, weekday=None, num_days=5):
    """HTML rows에서 식사 데이터를 파싱합니다.

    weekday가 None이면 주간 전체(num_days일치) dict 반환: {0..num_days-1: {meal: text}}
    weekday가 지정되면 해당 요일 dict 반환: {meal: text}
    """
    if weekday is not None:
        data = {m: "식단 정보 없음" for m in meal_types}
    else:
        data = {i: {m: "식단 정보 없음" for m in meal_types} for i in range(num_days)}

    for row in rows:
        header = row.find("th")
        if not header:
            continue
        header_text = header.get_text(strip=True)
        cells = row.find_all("td")

        matched_meal = next((m for m in meal_types if m in header_text), None)
        if not matched_meal:
            continue

        if weekday is not None:
            if len(cells) > weekday:
                text = "\n".join(
                    line.strip()
                    for line in cells[weekday].get_text(separator="\n").split("\n")
                    if line.strip()
                )
                data[matched_meal] = text or "식단 정보 없음"
        else:
            for i in range(num_days):
                if len(cells) > i:
                    text = "\n".join(
                        line.strip()
                        for line in cells[i].get_text(separator="\n").split("\n")
                        if line.strip()
                    )
                    data[i][matched_meal] = text or "식단 정보 없음"

    return data


def get_diet_by_day(day_offset=0, dorm="haeoreum"):
    """오늘 기준 day_offset일 후의 식단을 텍스트로 반환합니다."""
    config = DORM_CONFIG.get(dorm)
    if not config:
        return f"알 수 없는 기숙사입니다: {dorm}"

    target_date = datetime.now(KST) + timedelta(days=day_offset)
    weekday = target_date.weekday()  # 0:월 ~ 6:일

    if weekday > 4 and not config.get("has_weekend"):
        return f"[{config['name']}] 주말에는 식단이 없습니다."

    date_str = target_date.strftime("%Y-%m-%d")
    cache_key = (dorm, date_str)
    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        html = _fetch_diet_html(config)
        soup = BeautifulSoup(html, "html.parser")

        rows = soup.select("table.week_menu_tbl tbody tr")
        if not rows:
            return f"[{config['name']}] 식단 데이터를 찾을 수 없습니다."

        meal_types = config["meals"]
        data = _parse_meals(rows, meal_types, weekday=weekday)

        lines = [f"[{config['name']} {target_date.strftime('%m/%d')} 식단]"]
        for meal in meal_types:
            emoji = _MEAL_EMOJI[meal]
            meal_label = _meal_label(config, meal, weekday)
            lines.append(f"\n{emoji} {meal_label}:\n{data[meal]}")

        result = "\n".join(lines)
        _set_cached(cache_key, result)
        return result

    except requests.exceptions.Timeout:
        return "식단 서버 응답이 없습니다. 잠시 후 다시 시도해주세요."
    except requests.exceptions.RequestException as e:
        print(f"[crawler] 네트워크 오류: {e}")
        return "네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    except Exception as e:
        print(f"[crawler] 오류: {e}")
        return "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."


def get_today_meals(dorm="haeoreum"):
    return get_diet_by_day(0, dorm)


def get_tomorrow_meals(dorm="haeoreum"):
    return get_diet_by_day(1, dorm)


def get_week_data(dorm="haeoreum"):
    """이미지 생성용 주간 식단 raw 데이터를 반환합니다.

    Returns:
        (config, monday, meals) 튜플, 또는 오류 발생 시 str
    """
    config = DORM_CONFIG.get(dorm)
    if not config:
        return f"알 수 없는 기숙사입니다: {dorm}"

    today = datetime.now(KST)
    monday = today - timedelta(days=today.weekday())
    cache_key = (dorm, monday.strftime("%Y-%m-%d"), "raw")

    cached = _get_cached(cache_key)
    if cached:
        return config, monday, cached

    try:
        html = _fetch_diet_html(config)
        soup = BeautifulSoup(html, "html.parser")
        rows = soup.select("table.week_menu_tbl tbody tr")
        if not rows:
            return f"[{config['name']}] 식단 데이터를 찾을 수 없습니다."
        num_days = 7 if config.get("has_weekend") else 5
        meals = _parse_meals(rows, config["meals"], num_days=num_days)
        _set_cached(cache_key, meals)
        return config, monday, meals
    except requests.exceptions.Timeout:
        return "식단 서버 응답이 없습니다. 잠시 후 다시 시도해주세요."
    except requests.exceptions.RequestException as e:
        print(f"[crawler] 네트워크 오류: {e}")
        return "네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    except Exception as e:
        print(f"[crawler] 오류: {e}")
        return "서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
