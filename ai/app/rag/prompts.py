"""Prompt templates.

The answering prompt is the main defence against a confident, uncited, wrong
answer. It does three things deliberately: numbers every context block so the
model has a concrete token to cite, forbids outside knowledge, and gives the
model an explicit, blameless way to say the lecture does not cover something --
without which a model will invent an answer rather than appear unhelpful.
"""

QA_SYSTEM = """You are a study assistant helping a student understand ONE specific lecture.

Rules you must follow:
1. Answer ONLY from the numbered context blocks provided. Never use outside knowledge,
   even if you are confident it is correct.
2. Cite the block you used inline, immediately after the claim it supports, like [1] or [2].
   Every factual sentence must carry a citation.
3. If the context does not contain the answer, reply with exactly:
   "The lecture does not cover this."
   Do not apologise, speculate, or offer related information.
4. Never cite a block number that was not provided to you.
5. Be concise. Two or three sentences is usually enough."""


def build_qa_prompt(question: str, blocks: list[tuple[int, str, str]]) -> str:
    """Render the user prompt.

    `blocks` is (marker, source_label, text). The source label is shown to the
    model so it can phrase answers naturally ("as shown on slide 4"), but the
    mapping back to a real citation is done in code, never trusted from output.
    """
    rendered = "\n\n".join(
        f"[{marker}] ({label})\n{text}" for marker, label, text in blocks
    )
    return f"""Context blocks from the lecture:

{rendered}

---
Student's question: {question}

Answer using only the blocks above, citing each claim as [n]."""


SUMMARY_SYSTEM = """You summarise lecture material for students revising it.

Return JSON with exactly these keys:
- "summary": 3-5 sentences covering what the lecture is about and its main argument.
- "key_concepts": 4-8 objects, each {"term": "...", "explanation": "..."}, where the
  term is a phrase a student would need to know and the explanation is one sentence.

Use only the provided material. Do not invent concepts that are not present."""


def build_summary_prompt(document_title: str, text: str) -> str:
    return f"""Lecture file: {document_title}

Material:
{text}

Produce the JSON summary."""
