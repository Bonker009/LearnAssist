"""Ollama chat provider."""

import json
import re

import httpx
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.llm.base import LLMProvider, T

# Models drift into ```json fences even in JSON mode.
_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json(raw: str) -> str:
    """Pull the JSON body out of a response that may be fenced or prose-wrapped."""
    fenced = _FENCE_RE.search(raw)
    if fenced:
        return fenced.group(1)
    start = min(
        (i for i in (raw.find("{"), raw.find("[")) if i != -1),
        default=-1,
    )
    if start == -1:
        return raw
    end = max(raw.rfind("}"), raw.rfind("]"))
    return raw[start : end + 1] if end > start else raw


class OllamaLLMProvider(LLMProvider):
    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_chat_model

    async def _chat(
        self, system: str, prompt: str, temperature: float, json_mode: bool
    ) -> str:
        payload: dict = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if json_mode:
            payload["format"] = "json"

        # Local inference on a 7B model is slow; a short timeout here produces
        # confusing "ingest failed" errors that are really just impatience.
        async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
            response = await client.post(f"{self._base_url}/api/chat", json=payload)
            response.raise_for_status()
            return response.json()["message"]["content"]

    async def complete(self, system: str, prompt: str, temperature: float = 0.2) -> str:
        return await self._chat(system, prompt, temperature, json_mode=False)

    async def complete_json(
        self, system: str, prompt: str, schema: type[T], temperature: float = 0.2
    ) -> T:
        last_error: Exception | None = None
        for attempt in range(2):
            raw = await self._chat(system, prompt, temperature, json_mode=True)
            try:
                return schema.model_validate_json(_extract_json(raw))
            except (ValidationError, json.JSONDecodeError) as exc:
                last_error = exc
                # Show the model its own mistake on the retry; a bare re-ask
                # usually reproduces the same malformed output.
                prompt = (
                    f"{prompt}\n\nYour previous reply was rejected: {exc}\n"
                    f"Reply with valid JSON matching the schema and nothing else."
                )
        raise ValueError(f"Model did not return valid JSON after 2 attempts: {last_error}")


def get_llm_provider() -> LLMProvider:
    """Single place to swap the provider (e.g. for OpenAI)."""
    return OllamaLLMProvider()


class KeyConcept(BaseModel):
    term: str
    explanation: str


class SummaryResult(BaseModel):
    summary: str
    key_concepts: list[KeyConcept]
