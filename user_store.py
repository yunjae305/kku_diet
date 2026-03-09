from google.cloud import firestore

_db = None


def _get_db():
    global _db
    if _db is None:
        _db = firestore.Client()
    return _db


def get_user_dorm(user_id):
    if not user_id:
        return None
    doc = _get_db().collection("users").document(user_id).get()
    return doc.get("dorm") if doc.exists else None


def set_user_dorm(user_id, dorm):
    if not user_id:
        return
    _get_db().collection("users").document(user_id).set(
        {"dorm": dorm, "updated_at": firestore.SERVER_TIMESTAMP},
        merge=True,
    )
