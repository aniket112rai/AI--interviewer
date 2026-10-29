from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skill: str
    score: int = Field(ge=0, le=100)
    comment: str


class QuestionFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str
    answer_summary: str
    feedback: str
    ideal_answer_points: list[str] = Field(default_factory=list)


class Report(BaseModel):
    model_config = ConfigDict(extra="forbid")

    overall_score: int = Field(ge=0, le=100)
    summary: str
    skill_scores: list[SkillScore] = Field(default_factory=list)
    strengths: list[str] = Field(min_length=3, max_length=3)
    gaps: list[str] = Field(min_length=3, max_length=3)
    question_feedback: list[QuestionFeedback] = Field(default_factory=list)
    communication_notes: str = ""
    next_steps: list[str] = Field(min_length=3, max_length=5)


class ReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    status: Literal["pending", "ready", "failed"]
    report: Report | None = None
