"""Versioned setup questions and validated records of explicit answers."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue, field_validator

_LEGACY_QUESTIONS: tuple[tuple[str, str], ...] = (
    ("repository", "Which GitHub repository will hold this project (owner/repository)?"),
    ("worker_runner", "Which coding CLI should implement tasks: codex, claude, or agy (Docker)?"),
    ("worker_model", "Which available model should the worker CLI use?"),
    (
        "reviewer_runner",
        "Which coding CLI should independently review tasks: codex, claude, or agy?",
    ),
    ("reviewer_model", "Which stronger available model should the reviewer CLI use?"),
    ("execution", "Which execution provider should this project use?"),
    ("image", "Which pinned container image should this environment use?"),
    ("allow_native", "Allow task commands to run natively on this host?"),
    ("resources", "Set max_parallel, memory_budget_mb and cpu_budget for this project."),
    ("test_resources", "Which registered external test resources are required?"),
    ("checks", "Which named verification commands should this project run?"),
    ("release_target", "Release to github-release, or none?"),
)

_QUESTIONS = (
    _LEGACY_QUESTIONS[0],
    ("providers", "Which coding providers should this project use: codex, claude or agy?"),
    (
        "models",
        "Choose a small worker and a large reviewer from your provider models. Medium is optional.",
    ),
    ("guidance", "Keep the default concise writing and simple-code rules, or change them?"),
    *_LEGACY_QUESTIONS[5:],
)

QUESTION_IDS = frozenset(key for key, _ in (*_QUESTIONS, *_LEGACY_QUESTIONS))


class AnswerRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    value: JsonValue
    source: Literal["explicit-answer"]
    recorded_at: str

    @field_validator("value")
    @classmethod
    def nonnull_value(cls, value: JsonValue) -> JsonValue:
        if value is None:
            raise ValueError("Invalid interview answer value")
        return value

    @field_validator("recorded_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        datetime.fromisoformat(value)
        return value


class InterviewState(BaseModel):
    # Older readers retained top-level extensions when saving another answer.
    model_config = ConfigDict(strict=True, extra="allow")

    schema_version: Literal[1, 2]
    answers: dict[str, AnswerRecord]

    @field_validator("schema_version", mode="before")
    @classmethod
    def integer_schema_version(cls, value: object) -> object:
        # Literal equality alone accepts True and floats as integer versions.
        if type(value) is not int:
            raise ValueError("schema_version must be an integer")
        return value

    @field_validator("answers")
    @classmethod
    def known_questions(cls, answers: dict[str, AnswerRecord]) -> dict[str, AnswerRecord]:
        if answers.keys() - QUESTION_IDS:
            raise ValueError("Invalid interview answer record")
        return answers

    @property
    def questions(self) -> tuple[tuple[str, str], ...]:
        return _QUESTIONS if self.schema_version == 2 else _LEGACY_QUESTIONS
