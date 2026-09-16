"""Ollama embedding provider (nomic-embed-text, 768-dim by default)."""

import asyncio

import httpx

from app.config import get_settings
from app.embeddings.base import EmbeddingProvider


class OllamaUnavailable(RuntimeError):
    """Ollama is missing, unreachable, or lacks the configured model."""


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
            try:
                response = await client.post(
                    f"{self._base_url}/api/embed",
                    json={"model": self._model, "input": texts},
                )
                response.raise_for_status()
            except httpx.ConnectError as exc:
                # By far the most common setup failure, and httpx's own message
                # ("All connection attempts failed") gives the reader nothing to
                # act on. Name the address and the fix instead.
                raise OllamaUnavailable(
                    f"Cannot reach Ollama at {self._base_url}. Start it on the host, or set "
                    f"OLLAMA_BASE_URL if it runs elsewhere."
                ) from exc
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 404:
                    raise OllamaUnavailable(
                        f"Ollama has no model named '{self._model}'. "
                        f"Run: ollama pull {self._model}"
                    ) from exc
                raise
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
