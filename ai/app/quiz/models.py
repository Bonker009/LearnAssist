"""Quiz shapes and validation.

Everything a model produces is treated as untrusted. A malformed question that
reaches a student is worse than a missing one: a quiz with two identical options,
or with an answer index pointing past the end of the list, is unanswerable and
destroys confidence in the rest of the set.
"""

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.models import SourceRef

OPTION_COUNT = 4


class GeneratedQuestion(BaseModel):
    """One question exactly as the model returned it, before validation."""

    question: str = Field(min_length=5, max_length=500)
    options: list[str]
    correct_index: int
    explanation: str = Field(default="", max_length=800)
    # Marker of the context block the question was drawn from; mapped back to a
    # real SourceRef in code, never trusted from the model.
    source_marker: int

    @field_validator("options")
    @classmethod
    def _exactly_four_distinct_options(cls, options: list[str]) -> list[str]:
        cleaned = [o.strip() for o in options if o and o.strip()]
        if len(cleaned) != OPTION_COUNT:
            raise ValueError(f"expected {OPTION_COUNT} options, got {len(cleaned)}")
        # Case-insensitive: "Mitosis" and "mitosis" as two choices is still
        # an unanswerable question.
        if len({o.casefold() for o in cleaned}) != OPTION_COUNT:
            raise ValueError("options must be distinct")
        return cleaned

    @model_validator(mode="after")
    def _answer_is_in_range(self) -> "GeneratedQuestion":
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError(
                f"correct_index {self.correct_index} is outside 0..{len(self.options) - 1}"
            )
        return self


class GeneratedQuiz(BaseModel):
    questions: list[GeneratedQuestion]


class QuizQuestion(BaseModel):
    """A validated question, bound to the source it came from.

    Serialised in camelCase because Spring Boot consumes it with Jackson. The
    nested `SourceRef` deliberately keeps its snake_case spelling: it is stored
    verbatim as JSON and passed straight through to the browser, whose TypeScript
    types expect `page_no` / `start_sec`.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    question: str
    options: list[str]
    correct_index: int
    explanation: str
    source: SourceRef
    source_label: str
    snippet: str


class QuizResponse(BaseModel):
    document_id: str
    questions: list[QuizQuestion]
