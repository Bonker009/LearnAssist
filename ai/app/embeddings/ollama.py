"""Ollama embedding provider (nomic-embed-text, 768-dim by default)."""

import asyncio

import httpx

from app.config import get_settings
from app.embeddings.base import EmbeddingProvider


class OllamaEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_embed_model
        self._dimension = settings.embed_dim
        self._batch_size = settings.embed_batch_size
        # Ollama serialises generation internally; unbounded fan-out just queues
        # requests and risks client-side timeouts on a slow local model.
        self._semaphore = asyncio.Semaphore(settings.embed_concurrency)

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _embed_batch(self, client: httpx.AsyncClient, texts: list[str]) -> list[list[float]]:
        async with self._semaphore:
            response = await client.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": texts},
            )
            response.raise_for_status()
            embeddings = response.json()["embeddings"]

        for vector in embeddings:
            if len(vector) != self._dimension:
                raise ValueError(
                    f"Model {self._model} returned {len(vector)}-dim vectors but the schema "
                    f"expects {self._dimension}. Changing embedding model requires a migration "
                    f"and a full re-index."
                )
        return embeddings

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        batches = [
            texts[i : i + self._batch_size] for i in range(0, len(texts), self._batch_size)
        ]
        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            results = await asyncio.gather(
                *(self._embed_batch(client, batch) for batch in batches)
            )
        return [vector for batch in results for vector in batch]

    async def embed_query(self, text: str) -> list[float]:
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            vectors = await self._embed_batch(client, [text])
        return vectors[0]


def get_embedding_provider() -> EmbeddingProvider:
    """Single place to swap the provider (e.g. for OpenAI)."""
    return OllamaEmbeddingProvider()
