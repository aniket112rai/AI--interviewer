from pydantic import BaseModel, ConfigDict, Field
from typing import Literal


class Evaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_idx: int = Field(ge=0)
    thread_id: str
    scored: bool = True
    answer_quality: Literal["strong", "partial", "weak", "unclear"] = "unclear"
    correctness: float | None = Field(default=None, ge=0, le=1)
    depth: float | None = Field(default=None, ge=0, le=1)
    communication: float | None = Field(default=None, ge=0, le=1)
    goals_covered: list[str] = Field(default_factory=list)
    missed_points: list[str] = Field(default_factory=list)
