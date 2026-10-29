from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlanText(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str


class Rubric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strong: str
    average: str
    weak: str


class PlanThread(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    phase: Literal["project", "tech", "behavioral"]
    topic: str
    weight: float = Field(gt=0)
    time_budget_sec: int = Field(default=1, gt=0)
    max_followups: int = Field(ge=0, le=3)
    difficulty_start: Literal["easy", "medium", "hard"]
    context: list[str] = Field(min_length=2, max_length=4)
    goals: list[str] = Field(min_length=2, max_length=4)
    rubric: Rubric
    seed_question: str = Field(min_length=12)


class Plan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opening: PlanText
    closing: PlanText
    opening_sec: int = Field(gt=0)
    closing_sec: int = Field(gt=0)
    threads: list[PlanThread] = Field(min_length=1)


class PlanSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    resume_id: str
    level: Literal["intern", "junior", "mid", "senior"]
    duration_min: Literal[15, 30, 45]


class PlanSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["planning", "ready", "failed", "live", "completed"]
    error: str | None = None


class SessionListItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    resume_filename: str | None = None
    level: Literal["intern", "junior", "mid", "senior"]
    duration_min: int
    status: Literal["planning", "ready", "failed", "live", "completed"]
    created_at: datetime
    overall_score: int | None = None
    report_status: Literal["pending", "ready", "failed"] | None = None


class SessionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    resume_id: str | None = None
    resume_filename: str | None = None
    level: Literal["intern", "junior", "mid", "senior"]
    duration_min: int
    status: Literal["planning", "ready", "failed", "live", "completed"]
    created_at: datetime
    topics: list[str] = Field(default_factory=list)
    error: str | None = None
