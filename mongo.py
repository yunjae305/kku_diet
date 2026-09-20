import os
from pymongo import MongoClient

_client = None
_SERVER_SELECTION_TIMEOUT_MS = int(os.environ.get("MONGO_SERVER_SELECTION_TIMEOUT_MS", "3000"))
_CONNECT_TIMEOUT_MS = int(os.environ.get("MONGO_CONNECT_TIMEOUT_MS", "3000"))
_SOCKET_TIMEOUT_MS = int(os.environ.get("MONGO_SOCKET_TIMEOUT_MS", "5000"))

DB_NAME = "kku_diet"


def get_collection(name):
    """kku_diet 데이터베이스의 컬렉션을 반환합니다.

    MongoClient는 프로세스당 한 번만 생성해 컬렉션끼리 연결 풀을 공유합니다.
    """
    global _client
    if _client is None:
        uri = os.environ.get("MONGODB_URI")
        if not uri:
            raise RuntimeError("MONGODB_URI 환경변수가 설정되지 않았습니다.")
        _client = MongoClient(
            uri,
            serverSelectionTimeoutMS=_SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=_CONNECT_TIMEOUT_MS,
            socketTimeoutMS=_SOCKET_TIMEOUT_MS,
        )
    return _client[DB_NAME][name]
