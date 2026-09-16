"""Embedding provider interface.

Every call site depends on this Protocol, never on Ollama directly, so swapping in
OpenAI later is a one-line change in the factory below.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Embed corpus text. Order of the result matches order of the input."""
        ...

    async def embed_query(self, text: str) -> list[float]:
        """Embed a user question.

        Kept separate from `embed_documents` because asymmetric models (nomic,
        bge) require a different prefix on each side; using the wrong one
        silently degrades recall.
        """
        ...
