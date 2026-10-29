from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class LiveState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    thread_idx: int = Field(default=0, ge=0)
    followups_used: int = Field(default=0, ge=0)
    difficulty: Literal["easy", "medium", "hard"] = "medium"
    strong_streak: int = Field(default=0, ge=0)
    weak_streak: int = Field(default=0, ge=0)
    hints_used_in_thread: int = Field(default=0, ge=0)
    goals_covered: dict[str, list[str]] = Field(default_factory=dict)
    asked_questions: list[str] = Field(default_factory=list)
    thread_started_at_sec: float = Field(default=0, ge=0)


class LiveTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str
    url: str
    room: str


class SessionFinalizeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    job_id: str = Field(min_length=1, max_length=128)
    end_reason: Literal["candidate_disconnected", "time_limit", "agent_shutdown", "candidate_ended", "abandoned"]
    job_id: str | None = Field(default=None, max_length=128)
