"""Guardrails on the chat: asks the guard service (LLM Guard) about each question and
answer.

Questions are checked for prompt injection and toxicity before any retrieval or
model call; answers are checked for toxicity before they are cached or returned. A
flagged message gets a short, localised reply instead, and is logged. See
guard/app.py for the checks themselves.
"""

import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings
from app.lang import Language

logger = logging.getLogger(__name__)

_BLOCKED_QUESTION: dict[Language, str] = {
    "other": "I can't help with that request. Try asking about your study materials.",
    "km": "ខ្ញុំមិនអាចជួយសំណើនេះបានទេ។ សូមសួរអំពីឯកសារសិក្សារបស់អ្នក។",
}

_BLOCKED_ANSWER: dict[Language, str] = {
    "other": "I couldn't give a suitable answer to that. Try rephrasing your question.",
    "km": "ខ្ញុំមិនអាចផ្តល់ចម្លើយដែលសមរម្យបានទេ។ សូមសួរម្តងទៀតដោយប្រើពាក្យផ្សេង។",
}


def blocked_question_message(language: Language) -> str:
    return _BLOCKED_QUESTION[language]


def blocked_answer_message(language: Language) -> str:
    return _BLOCKED_ANSWER[language]


@dataclass
class Verdict:
    allowed: bool
    flagged: list[str] = field(default_factory=list)


async def check_question(
    question: str, transport: httpx.AsyncBaseTransport | None = None
) -> Verdict:
    return await _scan("/scan/prompt", {"text": question}, transport)


async def check_answer(
    question: str, answer: str, transport: httpx.AsyncBaseTransport | None = None
) -> Verdict:
    return await _scan("/scan/output", {"prompt": question, "text": answer}, transport)


async def _scan(
    path: str, payload: dict, transport: httpx.AsyncBaseTransport | None
) -> Verdict:
    settings = get_settings()
    if not settings.guard_url:
        return Verdict(allowed=True)
    try:
        async with httpx.AsyncClient(
            base_url=settings.guard_url,
            timeout=settings.guard_timeout_seconds,
            transport=transport,
        ) as client:
            response = await client.post(
                path, json=payload, headers={"X-Internal-Key": settings.internal_api_key}
            )
            response.raise_for_status()
            data = response.json()
            return Verdict(allowed=bool(data["valid"]), flagged=list(data.get("flagged", [])))
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        if settings.guard_fail_open:
            logger.warning("Guard unavailable (%s); letting %s through unchecked", exc, path)
            return Verdict(allowed=True)
        logger.error("Guard unavailable (%s); refusing %s", exc, path)
        return Verdict(allowed=False, flagged=["guard-unavailable"])
