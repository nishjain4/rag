"""Semantic cache of previously asked questions and the DAX that answered them."""

from typing import Optional
from uuid import uuid4

import chromadb

from config import CACHE_DISTANCE_THRESHOLD, QUERY_CACHE_COLLECTION
from embedding import embed_question


class QueryCache:
    def __init__(self, chroma_client):
        self._chroma_client = chroma_client
        self._collection = chroma_client.get_or_create_collection(
            name=QUERY_CACHE_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def reset(self) -> None:
        try:
            self._chroma_client.delete_collection(QUERY_CACHE_COLLECTION)
        except chromadb.errors.NotFoundError:
            pass
        self._collection = self._chroma_client.get_or_create_collection(
            name=QUERY_CACHE_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )

    def lookup(self, question: str, document_name: str) -> Optional[dict]:
        """Return the cached entry for a semantically equivalent past question."""
        if self._collection.count() == 0:
            return None

        result = self._collection.query(
            query_embeddings=[embed_question(question)],
            n_results=1,
            where={"document": document_name},
            include=["documents", "metadatas", "distances"],
        )

        documents = result["documents"][0]
        if not documents:
            return None

        distance = result["distances"][0][0]
        if distance > CACHE_DISTANCE_THRESHOLD:
            return None

        metadata = result["metadatas"][0][0] or {}
        return {
            "question": documents[0],
            "answer": metadata.get("answer", ""),
            "intent": metadata.get("intent", "dax"),
            "predicted_output": metadata.get("predicted_output", ""),
            "distance": distance,
        }

    def store(
        self,
        question: str,
        answer: str,
        document_name: str,
        intent: str,
        predicted_output: str = "",
    ) -> None:
        self._collection.add(
            ids=[str(uuid4())],
            documents=[question],
            embeddings=[embed_question(question)],
            metadatas=[{
                "document": document_name,
                "answer": answer,
                "intent": intent,
                "predicted_output": predicted_output,
            }],
        )
