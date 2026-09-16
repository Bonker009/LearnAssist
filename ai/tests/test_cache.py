"""Answer cache behaviour.

The cache must be invisible when it fails. Redis being down should make answers
slow, never absent -- so every path here is checked for degrading to a miss rather
than raising.
"""

import os
from uuid import uuid4

import pytest

from app import cache


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    # The module memoises its client; clear it so each test sees fresh env.
    monkeypatch.setattr(cache, "_client", None)
    yield
    cache._client = None


async def test_no_redis_configured_is_a_miss(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    assert await cache.get_answer(uuid4(), "any question") is None


async def test_write_without_redis_does_not_raise(monkeypatch):
    """A cache write failure must never fail the request that produced the answer."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    await cache.set_answer(uuid4(), "q", {"answer": "a", "citations": [], "grounded": True})


async def test_unreachable_redis_degrades_to_a_miss(monkeypatch):
    # A port nothing listens on: the client constructs fine and fails on use.
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:65530/0")
    assert await cache.get_answer(uuid4(), "q") is None
    await cache.set_answer(uuid4(), "q", {"answer": "a"})
    assert await cache.ping() is False


async def test_bump_generation_without_redis_is_silent(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    await cache.bump_generation(uuid4())


async def test_key_normalises_whitespace_and_case(monkeypatch):
    """The same question typed differently should hit the same entry."""
    monkeypatch.delenv("REDIS_URL", raising=False)
    document = uuid4()
    a = await cache._answer_key(document, "What is  the Calvin cycle?")
    b = await cache._answer_key(document, "what is the calvin CYCLE?  ")
    assert a == b


async def test_key_differs_by_document(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    question = "What is photosynthesis?"
    assert await cache._answer_key(uuid4(), question) != await cache._answer_key(
        uuid4(), question
    )


async def test_key_differs_by_question(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    document = uuid4()
    assert await cache._answer_key(document, "one") != await cache._answer_key(
        document, "two"
    )
