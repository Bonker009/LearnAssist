"""Answer cache.

Two students in the same course ask the same question about the same lecture, and
a local 32B model takes tens of seconds to answer it. Caching that is the single
cheapest improvement available.

The cache is deliberately fail-open: Redis being down must degrade to a slow
answer, never to no answer.
"""

import hashlib
import json
import logging
import os
from typing import Any
from uuid import UUID

import redis.asyncio as redis

logger = logging.getLogger(__name__)

_client: redis.Redis | None = None


def _get_client() -> redis.Redis | None:
    global _client
    if _client is None:
        url = os.getenv("REDIS_URL")
        if not url:
            return None
        _client = redis.from_url(url, decode_responses=True, socket_timeout=2)
    return _client


async def _generation(document_id: UUID) -> int:
    """Monotonic counter bumped whenever a document is re-indexed.

    Included in every cache key so a re-ingest cannot leave answers behind that
    cite chunks which no longer exist. Cheaper and far more reliable than trying
    to enumerate and delete a document's keys.
    """
    client = _get_client()
    if client is None:
        return 0
    try:
        value = await client.get(f"doc:{document_id}:generation")
        return int(value) if value else 0
    except Exception:  # noqa: BLE001
        return 0


async def bump_generation(document_id: UUID) -> None:
    """Invalidate everything cached for a document."""
    client = _get_client()
    if client is None:
        return
    try:
        await client.incr(f"doc:{document_id}:generation")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Could not bump cache generation: %s", exc)


async def get_answer(document_ids: list[UUID], question: str) -> dict[str, Any] | None:
    client = _get_client()
    if client is None:
        return None
    try:
        key = await _answer_key(document_ids, question)
        raw = await client.get(key)
        if raw:
            logger.debug("Answer cache hit for documents %s", document_ids)
            return json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Answer cache read failed: %s", exc)
    return None


async def set_answer(
    document_ids: list[UUID], question: str, payload: dict[str, Any]
) -> None:
    client = _get_client()
    if client is None:
        return
    try:
        ttl = int(os.getenv("ANSWER_CACHE_TTL_SECONDS", "86400"))
        key = await _answer_key(document_ids, question)
        await client.set(key, json.dumps(payload), ex=ttl)
    except Exception as exc:  # noqa: BLE001
        logger.debug("Answer cache write failed: %s", exc)


async def _answer_key(document_ids: list[UUID], question: str) -> str:
    """Key over the exact resource set, each at its current generation.

    Sorted, so attaching the same files in a different order shares answers. Every
    document's generation is included, so re-ingesting any one of them retires
    answers that might cite it.
    """
    scope = []
    for document_id in sorted({str(d) for d in document_ids}):
        scope.append(f"{document_id}@{await _generation(UUID(document_id))}")
    # Normalised so trailing whitespace and capitalisation do not split the cache
    # across what is really the same question.
    normalised = " ".join(question.lower().split())
    digest = hashlib.sha256(("|".join(scope) + "\n" + normalised).encode()).hexdigest()[:40]
    return f"answer:v2:{digest}"


async def ping() -> bool:
    client = _get_client()
    if client is None:
        return False
    try:
        return bool(await client.ping())
    except Exception:  # noqa: BLE001
        return False


async def close() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
