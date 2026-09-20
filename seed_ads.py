"""ads.json 내용을 MongoDB의 kku_diet.ads 컬렉션에 동기화합니다.

사용법:
    python seed_ads.py                  # ads.json 을 DB에 반영
    python seed_ads.py --list           # DB에 등록된 상품 목록 확인
    python seed_ads.py --file other.json
"""
import json
import os
import sys
from dotenv import load_dotenv

load_dotenv()

from pymongo.errors import PyMongoError

from ad_store import list_ads, sync_ads

DEFAULT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ads.json")
REQUIRED_FIELDS = ("ad_id", "title", "link")
DEFAULT_BUTTON_LABEL = "쿠팡에서 보기"
BUTTON_LABEL_MAX = 14  # 카카오 버튼 라벨 길이 제한


def load_ads(path):
    """ads.json을 읽어 검증한 뒤 DB에 넣을 형태로 정규화합니다."""
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, list):
        raise ValueError("ads.json의 최상위 값은 배열이어야 합니다.")

    seen = set()
    ads = []
    for index, item in enumerate(raw, start=1):
        where = f"{index}번째 항목"
        if not isinstance(item, dict):
            raise ValueError(f"{where}: 객체 형태가 아닙니다.")

        for field in REQUIRED_FIELDS:
            if not str(item.get(field, "")).strip():
                raise ValueError(f"{where}: '{field}' 값이 비어 있습니다.")

        ad_id = item["ad_id"].strip()
        if ad_id in seen:
            raise ValueError(f"{where}: ad_id '{ad_id}'가 중복됩니다.")
        seen.add(ad_id)

        link = item["link"].strip()
        if not link.startswith("https://"):
            raise ValueError(f"{where}: link는 https:// 로 시작해야 합니다.")

        label = (item.get("button_label") or DEFAULT_BUTTON_LABEL).strip()
        if len(label) > BUTTON_LABEL_MAX:
            raise ValueError(f"{where}: button_label은 {BUTTON_LABEL_MAX}자 이하여야 합니다.")

        ads.append({
            "ad_id": ad_id,
            "title": item["title"].strip(),
            "description": (item.get("description") or "").strip(),
            "image_url": (item.get("image_url") or "").strip(),
            "link": link,
            "button_label": label,
            "active": bool(item.get("active", True)),
        })
    return ads


def _resolve_path(argv):
    if "--file" not in argv:
        return DEFAULT_FILE
    index = argv.index("--file") + 1
    if index >= len(argv):
        raise ValueError("--file 뒤에 파일 경로를 적어주세요.")
    return argv[index]


def main(argv):
    if "--list" in argv:
        ads = list_ads()
        if not ads:
            print("등록된 상품이 없습니다.")
        for ad in ads:
            state = "ON " if ad.get("active") else "OFF"
            print(f"[{state}] {ad['ad_id']} | {ad['title']} | {ad['link']}")
        return 0

    ads = load_ads(_resolve_path(argv))
    if not ads and "--allow-empty" not in argv:
        print("ads.json이 비어 있습니다. DB의 상품을 모두 지우려면 --allow-empty를 붙여주세요.")
        return 1

    result = sync_ads(ads)
    active_count = sum(1 for ad in ads if ad["active"])
    print(f"동기화 완료 - 추가 {result['upserted']} / 수정 {result['updated']} / 삭제 {result['removed']}")
    print(f"활성 상품 {active_count}개 (전체 {len(ads)}개)")
    if active_count == 0:
        print("활성 상품이 없으면 추천 카드 대신 안내 메시지가 나갑니다. active를 true로 바꿔주세요.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except PyMongoError as e:
        print(f"DB 연결 실패 - {e.__class__.__name__}: {e}")
        sys.exit(1)
    except (ValueError, OSError) as e:
        print(f"오류: {e}")
        sys.exit(1)
