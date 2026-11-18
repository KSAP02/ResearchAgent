"""Milvus Lite vector store (a local file, no server needed).

Note: milvus-lite ships wheels for Linux and macOS only. On Windows, run the
backend through Docker (or WSL).
"""
from functools import lru_cache

from config import get_settings

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2; change when the embedding model is chosen


@lru_cache
def get_client():
    from pymilvus import MilvusClient  # lazy import so the app can start without it during tests

    return MilvusClient(get_settings().milvus_uri)


def init_vector_store() -> None:
    client = get_client()
    name = get_settings().milvus_collection
    if not client.has_collection(name):
        client.create_collection(collection_name=name, dimension=EMBEDDING_DIM, auto_id=True)
