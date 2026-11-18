"""Milvus Lite vector store (a local file, no server needed).

Milvus Lite has no Windows wheels, so it runs only inside the Docker container.
Vector dimension comes from config.toml [embeddings].dimension.
"""
import logging
from functools import lru_cache

from config import get_settings

log = logging.getLogger(__name__)


@lru_cache
def get_client():
    from pymilvus import MilvusClient

    return MilvusClient(get_settings().milvus_uri)


def _collection_dim(client, name: str) -> int | None:
    for field in client.describe_collection(name).get("fields", []):
        dim = field.get("params", {}).get("dim")
        if dim:
            return int(dim)
    return None


def init_vector_store() -> None:
    s = get_settings()
    client = get_client()
    name, dim = s.storage.milvus_collection, s.embeddings.dimension

    if client.has_collection(name):
        existing = _collection_dim(client, name)
        if existing == dim:
            return
        rows = int(client.get_collection_stats(name).get("row_count", 0))
        if rows:
            raise RuntimeError(
                f"Milvus collection '{name}' has dim={existing} with {rows} rows, but config "
                f"expects dim={dim}. Set a new [storage].milvus_collection or reset the volume "
                f"(docker compose down -v)."
            )
        log.warning("Recreating empty collection '%s' (dim %s -> %s)", name, existing, dim)
        client.drop_collection(name)

    client.create_collection(
        collection_name=name,
        dimension=dim,
        metric_type=s.retrieval.metric,
        auto_id=True,
    )
