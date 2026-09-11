from functools import lru_cache
from uuid import uuid4

from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    return SentenceTransformer(EMBEDDING_MODEL)


def embed_texts(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    return _get_model().encode(texts, normalize_embeddings=True).tolist()


def embed_question(question: str) -> list[float]:
    return embed_texts([question])[0]


def store_chunks(collection, chunks: list[dict]) -> None:
    if not chunks:
        return

    documents = [chunk["content"] for chunk in chunks]
    metadatas = [chunk.get("metadata", {}) for chunk in chunks]
    ids = [
        str(metadata.get("chunk_id") or uuid4())
        for metadata in metadatas
    ]

    collection.add(
        ids=ids,
        documents=documents,
        metadatas=metadatas,
        embeddings=embed_texts(documents),
    )
