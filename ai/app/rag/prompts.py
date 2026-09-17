"""Prompt templates.

The answering prompt is the main defence against a confident, uncited, wrong
answer. It does three things deliberately: numbers every context block so the
model has a concrete token to cite, forbids outside knowledge, and gives the
model an explicit, blameless way to say the lecture does not cover something --
without which a model will invent an answer rather than appear unhelpful.
"""

import re

_MARKER_RE = re.compile(r"\s?\[\d{1,3}\]")

QA_SYSTEM = """You are a study assistant. A student is chatting with you about the study
materials they attached to this chat: lecture files, recordings, web pages and notes.

Rules you must follow:
1. Answer ONLY from the numbered context blocks provided. Never use outside knowledge,
   even if you are confident it is correct.
2. Cite the block you used inline, immediately after the claim it supports, like [1] or [2].
   Every factual sentence must carry a citation.
3. If the context does not contain the answer, reply with exactly this English sentence
   and nothing else, whatever language the student wrote in:
   "The materials do not cover this."
   Do not apologise, speculate, or offer related information.
4. Never cite a block number that was not provided to you.
5. Write the answer in the language the prompt tells you to use, even when the context
   blocks are in a different language. Keep technical terms from the material in their
   original form, in parentheses after the translation, when that helps the student
   match them to the lecture.
6. The earlier conversation, if shown, is only for understanding what the student is
   referring to. It is not a source: facts must still come from the context blocks.
7. Be concise. Two to four sentences is usually enough."""


_LANGUAGE_INSTRUCTIONS = {
    "km": "Write your answer in Khmer (ភាសាខ្មែរ).",
    "other": "Write your answer in the same language as the student's question.",
}


def build_qa_prompt(
    question: str,
    blocks: list[tuple[int, str, str]],
    history: list[tuple[str, str]] | None = None,
    language: str = "other",
) -> str:
    """Render the user prompt.

    `blocks` is (marker, source_label, text). The source label is shown to the
    model so it can phrase answers naturally ("as shown on slide 4"), but the
    mapping back to a real citation is done in code, never trusted from output.

    `history` is (role, content) for earlier turns. Citation markers are stripped
    from it: an old "[2]" refers to a block from a previous retrieval, and leaving
    it in invites the model to copy a number that now means something else.
    """
    rendered = "\n\n".join(
        f"[{marker}] ({label})\n{text}" for marker, label, text in blocks
    )

    conversation = ""
    if history:
        lines = []
        for role, content in history:
            speaker = "Student" if role == "USER" else "Assistant"
            lines.append(f"{speaker}: {_MARKER_RE.sub('', content).strip()}")
        conversation = "Earlier in this conversation:\n" + "\n".join(lines) + "\n\n---\n"

    return f"""Context blocks from the student's materials:

{rendered}

---
{conversation}Student's question: {question}

Answer using only the blocks above, citing each claim as [n].
{_LANGUAGE_INSTRUCTIONS.get(language, _LANGUAGE_INSTRUCTIONS["other"])}"""


SUMMARY_SYSTEM = """You summarise lecture material for students revising it.

Return JSON with exactly these keys:
- "summary": 3-5 sentences covering what the lecture is about and its main argument.
- "key_concepts": 4-8 objects, each {"term": "...", "explanation": "..."}, where the
  term is a phrase a student would need to know and the explanation is one sentence.

Use only the provided material. Do not invent concepts that are not present.
Write in the language the material is written in (for example, Khmer material gets a
Khmer summary), keeping the JSON keys in English."""


def build_summary_prompt(document_title: str, text: str) -> str:
    return f"""Lecture file: {document_title}

Material:
{text}

Produce the JSON summary."""
