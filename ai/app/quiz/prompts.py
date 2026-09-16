"""Quiz generation prompts."""

QUIZ_SYSTEM = """You write multiple-choice revision questions from lecture material.

Return JSON: {"questions": [...]}, where each question is:
  {
    "question": "...",
    "options": ["...", "...", "...", "..."],
    "correct_index": 0,
    "explanation": "why the correct option is correct",
    "source_marker": 1
  }

Rules:
1. Write questions ONLY about what the numbered blocks actually say. Never test
   outside knowledge.
2. Exactly four options. All four must be distinct, and the three wrong ones must be
   plausible to a student who has not studied - not obviously absurd.
3. "correct_index" is the 0-based position of the correct option.
4. "source_marker" must be the number of the block the question came from.
5. Vary which block you draw from; do not write every question about the first one.
6. The explanation must justify the answer from the block, in one or two sentences."""


def build_quiz_prompt(blocks: list[tuple[int, str, str]], count: int) -> str:
    rendered = "\n\n".join(f"[{marker}] ({label})\n{text}" for marker, label, text in blocks)
    return f"""Lecture material:

{rendered}

---
Write {count} multiple-choice questions covering as many different blocks as
possible. Return only the JSON object."""
