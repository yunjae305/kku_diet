from PIL import Image, ImageDraw, ImageFont
import io
import os
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

_FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
_FONT_FILE = os.path.join(_FONT_DIR, "NanumGothic.ttf")
_TMP_FONT = "/tmp/NanumGothic.ttf"

# 한글 폰트 탐색 경로 (우선순위 순)
_FONT_CANDIDATES = [
    _FONT_FILE,                                                             # 프로젝트 내 (레포 포함, 최우선)
    _TMP_FONT,                                                              # Linux /tmp
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",                     # Ubuntu 시스템
    "/usr/share/fonts/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",                                          # Windows (로컬 개발)
    "C:/Windows/Fonts/gulim.ttc",
]

_font_path = None  # 지연 초기화


def _ensure_font():
    """한글 폰트 경로를 반환합니다. 폰트가 없으면 GitHub에서 자동 다운로드합니다."""
    global _font_path

    # 이미 찾은 경우 재사용
    if _font_path and os.path.exists(_font_path):
        return _font_path

    found = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)
    if found:
        _font_path = found
        return _font_path

    # 자동 다운로드 (폴백)
    save_path = _TMP_FONT if os.name != "nt" else _FONT_FILE
    try:
        import urllib.request
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        url = "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
        print("[image_gen] 한글 폰트 다운로드 중...")
        urllib.request.urlretrieve(url, save_path)
        print("[image_gen] 폰트 다운로드 완료")
        _font_path = save_path
        return _font_path
    except Exception as e:
        print(f"[image_gen] 폰트 다운로드 실패: {e}")
        return None


def _font(size):
    """지정된 크기의 폰트 객체를 반환합니다. 폰트 로드 실패 시 기본 폰트 사용."""
    path = _ensure_font()
    if path:
        try:
            return ImageFont.truetype(path, size)
        except Exception as e:
            print(f"[image_gen] 폰트 로드 실패: {e}")
    return ImageFont.load_default()


# ── 레이아웃 상수 ──────────────────────────────────────────────
_PAD = 14       # 외부 여백
_LABEL_W = 52   # 식사 레이블 열 너비
_COL_W = 158    # 요일 열 너비
_TITLE_H = 48   # 제목 바 높이
_HEAD_H = 38    # 요일 헤더 행 높이
_LINE_H = 17    # 텍스트 한 줄 높이
_CELL_PAD = 7   # 셀 내부 여백

# ── 색상 상수 ─────────────────────────────────────────────────
_C_TITLE_BG = "#1B5E20"   # 제목 배경 (진한 녹색)
_C_TITLE_FG = "#FFFFFF"
_C_HEAD_BG  = "#388E3C"   # 요일 헤더 배경
_C_HEAD_FG  = "#FFFFFF"
_C_LABEL_BG = "#E8F5E9"   # 식사 레이블 배경 (연한 녹색)
_C_LABEL_FG = "#2E7D32"
_C_TODAY_BG = "#FFFDE7"   # 오늘 컬럼 배경 (연한 노랑)
_C_TODAY_HEAD = "#F9A825" # 오늘 헤더 강조색
_C_GRID     = "#BDBDBD"   # 구분선
_C_TEXT     = "#212121"   # 일반 텍스트
_C_BG       = "#FAFAFA"   # 전체 배경


def _cell_lines(text, max_items=8):
    """셀 텍스트를 줄 목록으로 변환합니다. 항목이 많으면 '외 N가지'로 축약합니다."""
    if not text or text == "식단 정보 없음":
        return ["식단 정보 없음"]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return ["식단 정보 없음"]
    if len(lines) > max_items:
        lines = lines[:max_items] + [f"외 {len(lines) - max_items}가지"]
    return lines


def generate_weekly_image(config, monday, meals):
    """주간 식단표 PNG 이미지를 생성합니다.

    Args:
        config: DORM_CONFIG 항목 (name, meals 포함)
        monday: datetime (해당 주 월요일)
        meals:  {0..4: {meal_type: "...", ...}}

    Returns:
        PNG 이미지 bytes
    """
    meal_types = config["meals"]
    day_names = ["월", "화", "수", "목", "금"]
    today_wd = datetime.now(KST).weekday()  # 오늘 요일 (0=월)

    font_cell  = _font(11)
    font_head  = _font(13)
    font_title = _font(16)

    # 각 식사 행의 높이: 가장 많은 항목 수 기준으로 계산
    row_heights = {}
    for meal in meal_types:
        max_lines = 1
        for i in range(5):
            lines = _cell_lines(meals[i].get(meal, "식단 정보 없음"))
            max_lines = max(max_lines, len(lines))
        row_heights[meal] = max_lines * _LINE_H + _CELL_PAD * 2

    W = _PAD * 2 + _LABEL_W + _COL_W * 5
    H = _PAD + _TITLE_H + _HEAD_H + sum(row_heights.values()) + _PAD

    img = Image.new("RGB", (W, H), _C_BG)
    d = ImageDraw.Draw(img)

    # ── 제목 바 ───────────────────────────────────────────────
    friday = monday + timedelta(days=4)
    title = f"{config['name']}  {monday.strftime('%m/%d')}(월) ~ {friday.strftime('%m/%d')}(금)"
    d.rectangle([0, 0, W, _TITLE_H], fill=_C_TITLE_BG)
    try:
        bbox = d.textbbox((0, 0), title, font=font_title)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = len(title) * 9, 16
    d.text(((W - tw) // 2, (_TITLE_H - th) // 2), title, font=font_title, fill=_C_TITLE_FG)

    # ── 요일 헤더 행 ──────────────────────────────────────────
    y = _TITLE_H
    d.rectangle([0, y, W, y + _HEAD_H], fill=_C_HEAD_BG)
    for i in range(5):
        x = _PAD + _LABEL_W + _COL_W * i
        date = monday + timedelta(days=i)
        label = f"{day_names[i]}  {date.strftime('%m/%d')}"
        is_today = (i == today_wd)
        if is_today:
            d.rectangle([x, y, x + _COL_W, y + _HEAD_H], fill=_C_TODAY_HEAD)
            fg = "#FFFFFF"
        else:
            fg = _C_HEAD_FG
        try:
            bbox = d.textbbox((0, 0), label, font=font_head)
            lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            lw, lh = len(label) * 7, 13
        d.text((x + (_COL_W - lw) // 2, y + (_HEAD_H - lh) // 2), label, font=font_head, fill=fg)

    # 세로 구분선 그리기
    table_top = _TITLE_H
    table_bottom = H - _PAD
    d.line([_PAD, table_top, _PAD, table_bottom], fill=_C_GRID, width=1)
    for i in range(6):
        x = _PAD + _LABEL_W + _COL_W * i
        d.line([x, table_top, x, table_bottom], fill=_C_GRID, width=1)

    # ── 식사별 데이터 행 ──────────────────────────────────────
    y = _TITLE_H + _HEAD_H
    for meal in meal_types:
        rh = row_heights[meal]

        # 식사 레이블 셀 (좌측)
        d.rectangle([_PAD, y, _PAD + _LABEL_W, y + rh], fill=_C_LABEL_BG)
        try:
            bbox = d.textbbox((0, 0), meal, font=font_head)
            lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            lw, lh = len(meal) * 7, 13
        d.text((_PAD + (_LABEL_W - lw) // 2, y + (rh - lh) // 2), meal, font=font_head, fill=_C_LABEL_FG)

        # 요일별 식단 셀
        for i in range(5):
            x = _PAD + _LABEL_W + _COL_W * i
            if i == today_wd:
                d.rectangle([x, y, x + _COL_W, y + rh], fill=_C_TODAY_BG)
            lines = _cell_lines(meals[i].get(meal, "식단 정보 없음"))
            ty = y + _CELL_PAD
            for line in lines:
                d.text((x + _CELL_PAD, ty), line, font=font_cell, fill=_C_TEXT)
                ty += _LINE_H

        # 행 구분선
        d.line([_PAD, y + rh, _PAD + _LABEL_W + _COL_W * 5, y + rh], fill=_C_GRID, width=1)
        y += rh

    # 테이블 외곽선
    d.rectangle(
        [_PAD, _TITLE_H, _PAD + _LABEL_W + _COL_W * 5, H - _PAD],
        outline=_C_GRID, width=1
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
