from mongo import get_collection

_col = None


def _get_col():
    global _col
    if _col is None:
        _col = get_collection("users")
        _col.create_index("user_id", unique=True)
    return _col


def get_user_dorm(user_id):
    if not user_id:
        return None
    doc = _get_col().find_one({"user_id": user_id}, {"dorm": 1})
    return doc["dorm"] if doc else None


def set_user_dorm(user_id, dorm):
    if not user_id:
        return
    _get_col().update_one(
        {"user_id": user_id},
        {"$set": {"dorm": dorm}},
        upsert=True,
    )
