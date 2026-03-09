"""
건국대학교 글로컬캠퍼스 기숙사 식단 크롤러
해오름학사 + 모시래학사 지원
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import Optional

# 상수 정의
BASE_URL = "https://dorm.kku.ac.kr/weekly_diet.do"

# 기숙사별 설정
DORM_CONFIG = {
    "haeoreum": {
        "name": "해오름학사",
        "short": "해오름",
        "main_url": "https://dorm.kku.ac.kr/main.do?dormType=H",
        "params": {"menuSeq": "43885", "bachelor": "HA"},
        "referer": "https://dorm.kku.ac.kr/main.do?dormType=H"
    },
    "mosirae": {
        "name": "모시래학사",
        "short": "모시래",
        "main_url": "https://dorm.kku.ac.kr/main.do?dormType=M",
        "params": {"menuSeq": "43860", "bachelor": "MO"},
        "referer": "https://dorm.kku.ac.kr/main.do?dormType=M"
    }
}

# 기본 헤더 (Referer는 동적으로 설정)
BASE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}

# 요일 매핑 (월=0 ~ 일=6)
WEEKDAY_NAMES = ["월", "화", "수", "목", "금", "토", "일"]

# 식사 타입별 행 인덱스 (tbody 내 tr 순서)
MEAL_ROW_INDEX = {
    "조식": 0,
    "점심": 1,
    "석식": 2
}


def get_diet(day_offset: int = 0, meal_type: str = "점심", dorm: str = "haeoreum") -> str:
    """
    식단 정보를 크롤링하여 반환합니다.

    Args:
        day_offset: 오늘 기준 날짜 오프셋 (0=오늘, 1=내일, -1=어제)
        meal_type: 식사 종류 ("조식", "점심", "석식")
        dorm: 기숙사 종류 ("haeoreum" 또는 "mosirae")

    Returns:
        포맷팅된 식단 정보 문자열
    """
    # 기숙사 설정 가져오기
    config = DORM_CONFIG.get(dorm, DORM_CONFIG["haeoreum"])
    dorm_name = config["short"]

    target_date = datetime.now() + timedelta(days=day_offset)
    weekday = target_date.weekday()  # 월=0 ~ 일=6
    date_str = target_date.strftime("%m월 %d일")
    day_name = WEEKDAY_NAMES[weekday]

    # 주말 체크 (토=5, 일=6) - 모시래는 주말에도 운영
    if dorm == "haeoreum" and weekday >= 5:
        return f"[{dorm_name}] {date_str}({day_name})은 식단이 없습니다."

    try:
        # 헤더 설정
        headers = BASE_HEADERS.copy()
        headers["Referer"] = config["referer"]

        # 세션으로 접근 (메인 페이지 먼저 방문 필요)
        session = requests.Session()
        session.get(config["main_url"], headers=headers, timeout=10)

        # 요청
        response = session.get(BASE_URL, params=config["params"], headers=headers, timeout=10)
        response.raise_for_status()
        response.encoding = 'utf-8'

        soup = BeautifulSoup(response.text, 'html.parser')

        # 식단 테이블 찾기
        table = soup.find('table', class_='week_menu_tbl')
        if not table:
            return f"[{dorm_name}] 식단 테이블을 찾을 수 없습니다."

        tbody = table.find('tbody')
        if not tbody:
            return f"[{dorm_name}] 식단 데이터를 찾을 수 없습니다."

        rows = tbody.find_all('tr')
        meal_row_idx = MEAL_ROW_INDEX.get(meal_type, 1)

        if meal_row_idx >= len(rows):
            return f"[{dorm_name}] {meal_type} 정보를 찾을 수 없습니다."

        meal_row = rows[meal_row_idx]
        cells = meal_row.find_all('td')

        # 요일에 해당하는 셀 선택 (월=0 ~ 일=6)
        if weekday >= len(cells):
            return f"[{dorm_name}] {date_str}({day_name}) {meal_type} 정보가 없습니다."

        target_cell = cells[weekday]

        # <br> 태그를 줄바꿈으로 변환하여 메뉴 추출
        menu_text = _parse_menu_cell(target_cell)

        if not menu_text:
            return f"[{dorm_name}] {date_str}({day_name}) {meal_type} 식단이 등록되지 않았습니다."

        # 결과 포맷팅
        return _format_response(date_str, day_name, meal_type, menu_text, dorm_name)

    except requests.Timeout:
        return f"[{dorm_name}] 서버 응답 시간이 초과되었습니다.\n잠시 후 다시 시도해주세요."
    except requests.RequestException:
        return f"[{dorm_name}] 식단 정보를 불러오는 중 오류가 발생했습니다.\n잠시 후 다시 시도해주세요."
    except Exception:
        return f"[{dorm_name}] 식단 조회 중 문제가 발생했습니다.\n잠시 후 다시 시도해주세요."


def _parse_menu_cell(cell) -> Optional[str]:
    """
    셀 내용을 파싱하여 메뉴 텍스트를 추출합니다.
    """
    text = cell.get_text(separator='\n')
    lines = [line.strip() for line in text.split('\n')]
    lines = [line for line in lines if line]

    if not lines:
        return None

    return '\n'.join(lines)


def _format_response(date_str: str, day_name: str, meal_type: str, menu_text: str, dorm_name: str = "") -> str:
    """
    카카오톡에 보기 좋게 응답을 포맷팅합니다.
    """
    if dorm_name:
        header = f"[ {dorm_name} {date_str}({day_name}) {meal_type} ]"
    else:
        header = f"[ {date_str}({day_name}) {meal_type} ]"
    divider = "─" * 20

    return f"{header}\n{divider}\n{menu_text}"


# === 해오름학사 편의 함수 ===

def get_daily_meals(day_offset: int = 0, dorm: str = "haeoreum") -> str:
    """해당 날짜의 점심과 저녁 메뉴를 함께 반환합니다."""
    lunch = get_diet(day_offset=day_offset, meal_type="점심", dorm=dorm)
    dinner = get_diet(day_offset=day_offset, meal_type="석식", dorm=dorm)
    return f"{lunch}\n\n{dinner}"


def get_today_meals(dorm: str = "haeoreum") -> str:
    """오늘 점심 + 저녁 메뉴를 반환합니다."""
    return get_daily_meals(day_offset=0, dorm=dorm)


def get_tomorrow_meals(dorm: str = "haeoreum") -> str:
    """내일 점심 + 저녁 메뉴를 반환합니다."""
    return get_daily_meals(day_offset=1, dorm=dorm)


# === 해오름학사 전용 ===

def get_haeoreum_today() -> str:
    """해오름학사 오늘 식단"""
    return get_today_meals(dorm="haeoreum")


def get_haeoreum_tomorrow() -> str:
    """해오름학사 내일 식단"""
    return get_tomorrow_meals(dorm="haeoreum")


# === 모시래학사 전용 ===

def get_mosirae_today() -> str:
    """모시래학사 오늘 식단"""
    return get_today_meals(dorm="mosirae")


def get_mosirae_tomorrow() -> str:
    """모시래학사 내일 식단"""
    return get_tomorrow_meals(dorm="mosirae")


# 테스트용
if __name__ == "__main__":
    print("=== 해오름학사 오늘 ===")
    print(get_haeoreum_today())
    print()
    print("=== 모시래학사 오늘 ===")
    print(get_mosirae_today())
