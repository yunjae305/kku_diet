import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

BASE_URL = "https://dorm.kku.ac.kr"

DORM_CONFIG = {
    "haeoreum": {
        "name": "해오름학사",
        "dorm_type": "H",
        "params": {"menuSeq": "43885", "bachelor": "HA"},
    },
    "mosirae": {
        "name": "모시래학사",
        "dorm_type": "M",
        "params": {"menuSeq": "43860", "bachelor": "MO"},
    },
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

# TTL 캐시: (dorm, date_str) -> (timestamp, result)
_cache: dict = {}
_CACHE_TTL = 600  # 10분


def _get_cached(key):
    if key in _cache:
        ts, value = _cache[key]
        if time.time() - ts < _CACHE_TTL:
            return value
        del _cache[key]
    return None


def _fetch_diet_html(config: dict) -> str:
    """세션을 통해 식단 페이지 HTML을 가져옵니다."""
    session = requests.Session()
    session.headers.update(_HEADERS)
    dorm_type = config["dorm_type"]

    # 1) landing 방문 → JSESSIONID 획득
    session.get(f"{BASE_URL}/landing.do", timeout=10)

    # 2) 기숙사 메인 페이지 방문 → dormType 세션 설정
    main_url = f"{BASE_URL}/main.do?dormType={dorm_type}"
    session.get(main_url, headers={"Referer": f"{BASE_URL}/landing.do"}, timeout=10)

    # 3) 식단 페이지 요청
    diet_url = f"{BASE_URL}/weekly_diet.do"
    response = session.get(
        diet_url,
        params=config["params"],
        headers={"Referer": main_url},
        timeout=10,
    )
    response.encoding = "utf-8"
    return response.text


def get_diet_by_day(day_offset=0, dorm="haeoreum"):
    config = DORM_CONFIG.get(dorm)
    if not config:
        return f"알 수 없는 기숙사입니다: {dorm}"

    target_date = datetime.now() + timedelta(days=day_offset)
    weekday = target_date.weekday()  # 0:월 ~ 6:일

    if weekday > 4:
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

        lunch = "식단 정보 없음"
        dinner = "식단 정보 없음"

        for row in rows:
            header = row.find("th")
            if not header:
                continue
            header_text = header.get_text(strip=True)
            cells = row.find_all("td")

            if "점심" in header_text and len(cells) > weekday:
                lunch = cells[weekday].get_text(separator="\n").strip()
            elif "저녁" in header_text and len(cells) > weekday:
                dinner = cells[weekday].get_text(separator="\n").strip()

        lunch = "\n".join(line.strip() for line in lunch.split("\n") if line.strip())
        dinner = "\n".join(line.strip() for line in dinner.split("\n") if line.strip())

        result = f"[{config['name']} {target_date.strftime('%m/%d')} 식단]\n\n🍴 점심:\n{lunch}\n\n🌙 저녁:\n{dinner}"
        _cache[cache_key] = (time.time(), result)
        return result

    except requests.exceptions.Timeout:
        return "식단 서버 응답이 없습니다. 잠시 후 다시 시도해주세요."
    except requests.exceptions.RequestException as e:
        print(f"[crawler] 네트워크 오류: {e}")
        return "네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    except Exception as e:
        print(f"[crawler] 오류: {e}")
        return "서버 오류가 발생했습니다. 터미널을 확인해주세요."


def get_today_meals(dorm="haeoreum"):
    return get_diet_by_day(0, dorm)


def get_tomorrow_meals(dorm="haeoreum"):
    return get_diet_by_day(1, dorm)


def get_week_meals(dorm="haeoreum"):
    config = DORM_CONFIG.get(dorm)
    if not config:
        return f"알 수 없는 기숙사입니다: {dorm}"

    today = datetime.now()
    monday = today - timedelta(days=today.weekday())
    cache_key = (dorm, monday.strftime("%Y-%m-%d"), "week")

    cached = _get_cached(cache_key)
    if cached:
        return cached

    try:
        html = _fetch_diet_html(config)
        soup = BeautifulSoup(html, "html.parser")

        rows = soup.select("table.week_menu_tbl tbody tr")
        if not rows:
            return f"[{config['name']}] 식단 데이터를 찾을 수 없습니다."

        meals = {i: {"lunch": "식단 정보 없음", "dinner": "식단 정보 없음"} for i in range(5)}

        for row in rows:
            header = row.find("th")
            if not header:
                continue
            header_text = header.get_text(strip=True)
            cells = row.find_all("td")

            for i in range(5):
                if len(cells) > i:
                    text = "\n".join(
                        line.strip() for line in cells[i].get_text(separator="\n").split("\n") if line.strip()
                    )
                    if "점심" in header_text:
                        meals[i]["lunch"] = text
                    elif "저녁" in header_text:
                        meals[i]["dinner"] = text

        day_names = ["월", "화", "수", "목", "금"]
        cards = []
        for i in range(5):
            date = monday + timedelta(days=i)
            lunch = ", ".join(meals[i]["lunch"].split("\n")) if meals[i]["lunch"] != "식단 정보 없음" else "식단 정보 없음"
            dinner = ", ".join(meals[i]["dinner"].split("\n")) if meals[i]["dinner"] != "식단 정보 없음" else "식단 정보 없음"
            desc = f"🍴 점심\n{lunch}\n\n🌙 저녁\n{dinner}"
            if len(desc) > 230:
                desc = desc[:227] + "..."
            cards.append({
                "title": f"{day_names[i]} ({date.strftime('%m/%d')})",
                "description": desc,
                "thumbnail": {
                    "imageUrl": "https://i.ibb.co/fdHxpF6Y/Authority-Mark.jpg"
                },
            })

        _cache[cache_key] = (time.time(), cards)
        return cards

    except requests.exceptions.Timeout:
        return "식단 서버 응답이 없습니다. 잠시 후 다시 시도해주세요."
    except requests.exceptions.RequestException as e:
        print(f"[crawler] 네트워크 오류: {e}")
        return "네트워크 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
    except Exception as e:
        print(f"[crawler] 오류: {e}")
        return "서버 오류가 발생했습니다. 터미널을 확인해주세요."
