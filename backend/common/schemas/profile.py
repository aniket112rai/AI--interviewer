from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Experience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = ""
    role: str = ""
    duration_months: int = Field(default=0, ge=0)
    tech: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class Project(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = ""
    description: str = ""
    stack: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)


class Profile(BaseModel):
    """Career profile only; never include candidate contact or identifying details."""

    model_config = ConfigDict(extra="forbid")

    summary: str = ""
    seniority: Literal["intern", "junior", "mid", "senior"] = "junior"
    total_experience_years: float = Field(default=0, ge=0)
    skills: list[str] = Field(default_factory=list)
    primary_stack: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    probe_targets: list[str] = Field(default_factory=list, min_length=3, max_length=6)


class ResumeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    filename: str
    status: Literal["parsing", "ready", "failed"]
    created_at: datetime
    summary: str | None = None
    error: str | None = None


class ResumeUploadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    status: Literal["parsing"]


class ResumeDetailResponse(ResumeResponse):
    profile: Profile | None = None
