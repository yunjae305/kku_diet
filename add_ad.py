"""쿠팡 파트너스 링크 하나를 ads.json에 추가하고 DB까지 반영합니다.

사용법:
    python add_ad.py "https://link.coupang.com/a/XXXX"
    python add_ad.py "<링크>" --title "보온 텀블러 500ml" --description "기숙사 필수템"
    python add_ad.py "<링크>" --image "https://.../thumb.jpg" --id tumbler-500

--title 또는 --image를 생략하면 링크를 열어 og:title, og:image를 읽어옵니다.
쿠팡이 자동 수집을 막는 경우가 있어 실패하면 직접 값을 넘겨야 합니다.
"""
import argparse
import io
import json
import os
import re
import sys
from urllib.parse import urlparse
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

import requests
from bs4 import BeautifulSoup
from pymongo.errors import PyMongoError

from ad_store import sync_ads
from seed_ads import DEFAULT_BUTTON_LABEL, DEFAULT_FILE, load_ads

FETCH_TIMEOUT_SEC = int(os.environ.get("AD_FETCH_TIMEOUT_SEC", "10"))
_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_metadata(link):
    """링크를 열어 og:title, og:image를 읽어옵니다. 실패하면 빈 값을 돌려줍니다."""
    try:
        res = requests.get(
            link,
            headers={"User-Agent": _BROWSER_UA, "Accept-Language": "ko-KR,ko;q=0.9"},
            timeout=FETCH_TIMEOUT_SEC,
            allow_redirects=True,
        )
        res.raise_for_status()
    except requests.RequestException as e:
        print(f"안내: 상품 정보를 읽지 못했습니다 ({e.__class__.__name__}).")
        return {}

    soup = BeautifulSoup(res.text, "html.parser")

    def meta(prop):
        tag = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
        return (tag.get("content") or "").strip() if tag else ""

    title = meta("og:title")
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()
    return {"title": title, "image_url": meta("og:image")}


def make_ad_id(link, title, taken):
    """링크나 제목에서 ad_id를 만들고, 이미 쓰인 값이면 번호를 붙입니다."""
    tail = urlparse(link).path.rstrip("/").split("/")[-1]
    if tail and re.fullmatch(r"[A-Za-z0-9_-]{4,40}", tail):
        base = tail.lower()
    else:
        base = re.sub(r"[^0-9a-z가-힣]+", "-", (title or "").lower()).strip("-")[:40]
    if not base:
        base = "ad-" + uuid4().hex[:8]

    ad_id = base
    suffix = 2
    while ad_id in taken:
        ad_id = f"{base}-{suffix}"
        suffix += 1
    return ad_id


def read_raw_ads(path):
    """ads.json 원본과 줄바꿈 방식을 함께 읽습니다."""
    if not os.path.exists(path):
        return [], "\r\n"
    data = io.open(path, "rb").read()
    newline = "\r\n" if b"\r\n" in data else "\n"
    return json.loads(data.decode("utf-8")), newline


def write_raw_ads(path, ads, newline):
    text = json.dumps(ads, ensure_ascii=False, indent=2) + "\n"
    io.open(path, "w", encoding="utf-8", newline=newline).write(text)


def parse_args(argv):
    parser = argparse.ArgumentParser(description="쿠팡 파트너스 링크를 상품 목록에 추가합니다.")
    parser.add_argument("link", help="쿠팡 파트너스 링크 (https://)")
    parser.add_argument("--title", help="상품명. 생략하면 링크에서 읽어옵니다.")
    parser.add_argument("--description", default="", help="카드 설명 한 줄")
    parser.add_argument("--image", help="썸네일 URL. 생략하면 링크에서 읽어옵니다.")
    parser.add_argument("--id", dest="ad_id", help="ad_id. 생략하면 자동 생성합니다.")
    parser.add_argument("--label", default=DEFAULT_BUTTON_LABEL, help="버튼 문구 (최대 14자)")
    parser.add_argument("--inactive", action="store_true", help="등록만 하고 노출하지 않습니다.")
    parser.add_argument("--no-fetch", action="store_true", help="링크에서 상품 정보를 읽지 않습니다.")
    parser.add_argument("--no-sync", action="store_true", help="ads.json만 수정하고 DB에는 반영하지 않습니다.")
    parser.add_argument("--file", default=DEFAULT_FILE, help="상품 목록 파일 경로")
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    link = args.link.strip()
    if not link.startswith("https://"):
        print("오류: 링크는 https:// 로 시작해야 합니다.")
        return 1

    ads, newline = read_raw_ads(args.file)
    for existing in ads:
        if existing.get("link") == link:
            print(f"오류: 이미 등록된 링크입니다 (ad_id: {existing.get('ad_id')}).")
            return 1

    title = (args.title or "").strip()
    image_url = (args.image or "").strip()
    if not args.no_fetch and (not title or not image_url):
        found = fetch_metadata(link)
        title = title or found.get("title", "")
        image_url = image_url or found.get("image_url", "")

    if not title:
        print("오류: 상품명을 읽지 못했습니다. --title \"상품명\" 으로 직접 넘겨주세요.")
        return 1

    ad_id = (args.ad_id or "").strip() or make_ad_id(link, title, {a.get("ad_id") for a in ads})
    ads.append({
        "ad_id": ad_id,
        "title": title,
        "description": args.description.strip(),
        "image_url": image_url,
        "link": link,
        "button_label": args.label.strip(),
        "active": not args.inactive,
    })

    write_raw_ads(args.file, ads, newline)
    validated = load_ads(args.file)  # 형식이 깨졌으면 여기서 걸립니다.
    print(f"ads.json에 추가했습니다 - ad_id: {ad_id} / 제목: {title}")
    if not image_url:
        print("안내: 썸네일이 없어 이미지 없는 카드로 나갑니다. --image 로 채울 수 있습니다.")

    if args.no_sync:
        print("DB 반영은 건너뛰었습니다. 나중에 python seed_ads.py 를 실행하세요.")
        return 0
    if not os.environ.get("MONGODB_URI"):
        print("안내: MONGODB_URI가 없어 DB에는 반영하지 못했습니다.")
        print(".env에 MONGODB_URI를 넣은 뒤 python seed_ads.py 를 실행하세요.")
        return 0

    try:
        result = sync_ads(validated)
    except PyMongoError as e:
        print(f"DB 반영 실패 - {e.__class__.__name__}: {e}")
        print("ads.json에는 추가됐습니다. 연결 문제를 고친 뒤 python seed_ads.py 를 실행하세요.")
        return 1

    print(f"DB 동기화 완료 - 추가 {result['upserted']} / 수정 {result['updated']} / 삭제 {result['removed']}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError) as e:
        print(f"오류: {e}")
        sys.exit(1)
