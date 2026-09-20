from mongo import get_collection

_col = None


def _get_col():
    global _col
    if _col is None:
        _col = get_collection("ads")
        _col.create_index("ad_id", unique=True)
    return _col


def get_random_ad():
    """활성화된 쿠팡 파트너스 상품 중 하나를 무작위로 반환합니다. 없으면 None."""
    docs = list(_get_col().aggregate([
        {"$match": {"active": True}},
        {"$sample": {"size": 1}},
    ]))
    return docs[0] if docs else None


def list_ads():
    """등록된 모든 상품을 ad_id 순으로 반환합니다."""
    return list(_get_col().find({}, {"_id": 0}).sort("ad_id", 1))


def sync_ads(ads):
    """ads.json 내용으로 컬렉션을 동기화합니다.

    목록에 있는 상품은 ad_id 기준으로 upsert하고,
    목록에 없는 기존 상품은 삭제해 파일과 DB 상태를 일치시킵니다.
    """
    col = _get_col()
    kept_ids = [ad["ad_id"] for ad in ads]
    upserted = 0
    updated = 0

    for ad in ads:
        result = col.update_one({"ad_id": ad["ad_id"]}, {"$set": ad}, upsert=True)
        if result.upserted_id is not None:
            upserted += 1
        elif result.modified_count:
            updated += 1

    removed = col.delete_many({"ad_id": {"$nin": kept_ids}}).deleted_count
    return {"upserted": upserted, "updated": updated, "removed": removed}
