"""LLM provider interface."""

from typing import Protocol, TypeVar, runtime_checkable

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@runtime_checkable
class LLMProvider(Protocol):
    async def complete(self, system: str, prompt: str, temperature: float = 0.2) -> str:
        """Free-text completion."""
        ...

    async def complete_json(
        self, system: str, prompt: str, schema: type[T], temperature: float = 0.2
    ) -> T:
        """Completion validated against a Pydantic model.

        Implementations must not trust the model to honour JSON mode — it will
        occasionally wrap output in prose or a code fence. Parsing is defensive
        and retried once before failing.
        """
        ...
