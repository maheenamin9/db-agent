from qdrant_client import QdrantClient, models

from app.config import get_settings


def get_client() -> QdrantClient:
    return QdrantClient(url=get_settings().qdrant_url)


def reset_collection(client: QdrantClient, name: str, vector_size: int) -> None:
    """Wipe-and-rebuild: drop the collection if it exists, then create it fresh.

    Simplest option for a project this size (per the task's own guidance) — no
    incremental updates, no stale points left behind from a previous deploy.
    """
    if client.collection_exists(name):
        client.delete_collection(name)
    client.create_collection(
        collection_name=name,
        vectors_config=models.VectorParams(size=vector_size, distance=models.Distance.COSINE),
    )


def upsert_points(client: QdrantClient, name: str, points: list[models.PointStruct]) -> None:
    client.upsert(collection_name=name, points=points)
