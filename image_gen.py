from PIL import Image, ImageDraw, ImageFont
import io
import os
from datetime import timedelta

_FONT_CANDIDATES = [
    os.path.join(os.path.dirname(__file__), "fonts", "NanumGothic.ttf"),  # 프로젝트 내 (Render 빌드 복사)
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",                     # Ubuntu 시스템
    "/usr/share/fonts/nanum/NanumGothic.ttf",
    "C:/Windows/Fonts/malgun.ttf",                                          # Windows
    "C:/Windows/Fonts/gulim.ttc",
]
_font_path = next((p for p in _FONT_CANDIDATES if os.path.exists(p)), None)


def _font(size):
    if _font_path:
        try:
            return ImageFont.truetype(_font_path, size)
        except Exception:
            pass
    return ImageFont.load_default()


# Layout
_PAD = 14
_LABEL_W = 52
_COL_W = 158
_TITLE_H = 48
_HEAD_H = 38
_LINE_H = 17
_CELL_PAD = 7

# Colors
_C_TITLE_BG = "#1B5E20"
_C_TITLE_FG = "#FFFFFF"
_C_HEAD_BG = "#388E3C"
_C_HEAD_FG = "#FFFFFF"
_C_LABEL_BG = "#E8F5E9"
_C_LABEL_FG = "#2E7D32"
_C_TODAY_BG = "#FFFDE7"
_C_TODAY_HEAD = "#F9A825"
_C_GRID = "#BDBDBD"
_C_TEXT = "#212121"
_C_BG = "#FAFAFA"


def _cell_lines(text, max_items=8):
    if not text or text == "식단 정보 없음":
        return ["식단 정보 없음"]
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines:
        return ["식단 정보 없음"]
    if len(lines) > max_items:
        lines = lines[:max_items] + [f"외 {len(lines) - max_items}가지"]
    return lines


def generate_weekly_image(config, monday, meals):
    """
    config: DORM_CONFIG entry (name, meals 포함)
    monday: datetime (해당 주 월요일)
    meals: {0..4: {meal_type: "...", ...}}
    Returns: PNG bytes
    """
    meal_types = config["meals"]
    day_names = ["월", "화", "수", "목", "금"]
    today_wd = monday.now().weekday()  # 0=Mon

    font_cell = _font(11)
    font_head = _font(13)
    font_title = _font(16)

    # 각 식사 행의 높이 계산 (가장 많은 항목 기준)
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

    # 제목 바
    friday = monday + timedelta(days=4)
    title = f"{config['name']}  {monday.strftime('%m/%d')}(월) ~ {friday.strftime('%m/%d')}(금)"
    d.rectangle([0, 0, W, _TITLE_H], fill=_C_TITLE_BG)
    try:
        bbox = d.textbbox((0, 0), title, font=font_title)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    except Exception:
        tw, th = len(title) * 9, 16
    d.text(((W - tw) // 2, (_TITLE_H - th) // 2), title, font=font_title, fill=_C_TITLE_FG)

    # 요일 헤더
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

    # 세로 구분선
    table_top = _TITLE_H
    table_bottom = H - _PAD
    d.line([_PAD, table_top, _PAD, table_bottom], fill=_C_GRID, width=1)
    for i in range(6):
        x = _PAD + _LABEL_W + _COL_W * i
        d.line([x, table_top, x, table_bottom], fill=_C_GRID, width=1)

    # 식사별 행
    y = _TITLE_H + _HEAD_H
    for meal in meal_types:
        rh = row_heights[meal]

        # 식사 레이블 셀
        d.rectangle([_PAD, y, _PAD + _LABEL_W, y + rh], fill=_C_LABEL_BG)
        try:
            bbox = d.textbbox((0, 0), meal, font=font_head)
            lw, lh = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            lw, lh = len(meal) * 7, 13
        d.text((_PAD + (_LABEL_W - lw) // 2, y + (rh - lh) // 2), meal, font=font_head, fill=_C_LABEL_FG)

        # 요일별 셀
        for i in range(5):
            x = _PAD + _LABEL_W + _COL_W * i
            if i == today_wd:
                d.rectangle([x, y, x + _COL_W, y + rh], fill=_C_TODAY_BG)
            lines = _cell_lines(meals[i].get(meal, "식단 정보 없음"))
            ty = y + _CELL_PAD
            for line in lines:
                d.text((x + _CELL_PAD, ty), line, font=font_cell, fill=_C_TEXT)
                ty += _LINE_H

        # 가로 구분선
        d.line([_PAD, y + rh, _PAD + _LABEL_W + _COL_W * 5, y + rh], fill=_C_GRID, width=1)
        y += rh

    # 외곽선
    d.rectangle([_PAD, _TITLE_H, _PAD + _LABEL_W + _COL_W * 5, H - _PAD],
                outline=_C_GRID, width=1)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf.getvalue()
