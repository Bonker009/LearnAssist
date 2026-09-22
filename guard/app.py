"""Guardrails for the chat: LLM Guard behind a small internal API.

The ai service asks this service about every student question before answering it,
and about every answer before returning it. It runs on its own because LLM Guard
pins a transformers version that conflicts with Qwen3-ASR's.

Checks:
- question: prompt injection (an attempt to override the assistant's rules, which
  matters doubly here because answers are built from student-supplied documents),
  and toxicity
- answer: toxicity

The classifier models are English-trained. The injection model in particular flags
ordinary Khmer questions as injections (3 of 4 in testing), so for mostly-Khmer text
it only sees the Latin-script words. That still catches the usual attack phrasing
("ignore all previous instructions", "system prompt", "you are now DAN") mixed into
Khmer, and leaves technical terms like "CUDA Toolkit" harmless. An injection written
entirely in Khmer is NOT detected; the answer prompt's rules and the citation checks
in the ai service remain the defence there. Tune thresholds with the env vars below,
using the scores this service logs.

Like the ai service, this is internal only: no published port, and every scan needs
the shared X-Internal-Key.
"""

import logging
import os
import re
import threading
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("guard")

INTERNAL_KEY = os.getenv("INTERNAL_API_KEY", "dev-internal-key-change-me")
INJECTION_THRESHOLD = float(os.getenv("GUARD_INJECTION_THRESHOLD", "0.92"))
TOXICITY_THRESHOLD = float(os.getenv("GUARD_TOXICITY_THRESHOLD", "0.8"))

_KHMER = re.compile(r"[ក-៿᧠-᧿]")
_LETTER = re.compile(r"[^\W\d_]")
_LATIN_WORD = re.compile(r"[A-Za-z][A-Za-z0-9'\-]*")


def _mostly_khmer(text: str) -> bool:
    """Same rule as the ai service's language detection: 30% Khmer letters or more."""
    letters = _LETTER.findall(text)
    return bool(letters) and len(_KHMER.findall(text)) / len(letters) >= 0.3


_scanners: tuple[list, list] | None = None
# Loading is slow and the models are not documented as thread-safe, so both loading
# and scanning go through one lock. Scans take a fraction of a second on CPU.
_lock = threading.Lock()


def _load() -> tuple[list, list]:
    global _scanners
    if _scanners is None:
        from llm_guard.input_scanners import PromptInjection, Toxicity
        from llm_guard.input_scanners.prompt_injection import MatchType as InjectionMatch
        from llm_guard.input_scanners.toxicity import MatchType as ToxicityMatch
        from llm_guard.output_scanners import Toxicity as OutputToxicity

        logger.info("Loading guard models")
        # FULL match: a question is at most 2,000 characters, and sentence matching
        # would need NLTK data downloaded at runtime.
        _scanners = (
            [
                PromptInjection(threshold=INJECTION_THRESHOLD, match_type=InjectionMatch.FULL),
                Toxicity(threshold=TOXICITY_THRESHOLD, match_type=ToxicityMatch.FULL),
            ],
            [OutputToxicity(threshold=TOXICITY_THRESHOLD, match_type=ToxicityMatch.FULL)],
        )
        logger.info("Guard models ready")
    return _scanners


def _warm() -> None:
    try:
        with _lock:
            _load()
    except Exception:  # noqa: BLE001 - a failed warm-up is retried on first scan
        logger.exception("Guard warm-up failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Download and load the models in the background so the port opens at once.
    threading.Thread(target=_warm, daemon=True).start()
    yield


app = FastAPI(title="LearnAssist Guard", lifespan=lifespan)


def require_internal_key(x_internal_key: str = Header(default="")) -> None:
    if x_internal_key != INTERNAL_KEY:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "bad internal key")


class PromptScan(BaseModel):
    text: str = Field(max_length=20_000)


class OutputScan(BaseModel):
    prompt: str = Field(max_length=20_000)
    text: str = Field(max_length=50_000)


class Verdict(BaseModel):
    valid: bool
    flagged: list[str]
    scores: dict[str, float]


def _verdict(kind: str, valid_by: dict[str, bool], scores: dict[str, float]) -> Verdict:
    flagged = sorted(name for name, ok in valid_by.items() if not ok)
    rounded = {name: round(score, 3) for name, score in scores.items()}
    log = logger.warning if flagged else logger.info
    log("%s scan: %s %s", kind, "FLAGGED " + ",".join(flagged) if flagged else "ok", rounded)
    return Verdict(valid=not flagged, flagged=flagged, scores=rounded)


def _scan_prompt(text: str) -> Verdict:
    from llm_guard import scan_prompt

    with _lock:
        (injection, toxicity), _ = _load()
        if not _mostly_khmer(text):
            _, valid_by, scores = scan_prompt([injection, toxicity], text, fail_fast=False)
            return _verdict("prompt", valid_by, scores)

        # Mostly Khmer: toxicity reads the whole text, injection only its Latin words.
        _, valid_by, scores = scan_prompt([toxicity], text, fail_fast=False)
        latin = " ".join(_LATIN_WORD.findall(text))
        if latin:
            _, injection_valid, injection_scores = scan_prompt([injection], latin, fail_fast=False)
            valid_by |= injection_valid
            scores |= injection_scores
    return _verdict("prompt (km)", valid_by, scores)


def _scan_output(prompt: str, text: str) -> Verdict:
    from llm_guard import scan_output

    with _lock:
        _, output_scanners = _load()
        _, valid_by, scores = scan_output(output_scanners, prompt, text, fail_fast=False)
    return _verdict("output", valid_by, scores)


@app.get("/health")
def health() -> dict:
    return {"ok": True, "ready": _scanners is not None}


@app.post("/scan/prompt", dependencies=[Depends(require_internal_key)])
async def scan_prompt_endpoint(body: PromptScan) -> Verdict:
    return await run_in_threadpool(_scan_prompt, body.text)


@app.post("/scan/output", dependencies=[Depends(require_internal_key)])
async def scan_output_endpoint(body: OutputScan) -> Verdict:
    return await run_in_threadpool(_scan_output, body.prompt, body.text)
