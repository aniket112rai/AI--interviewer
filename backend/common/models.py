from datetime import UTC, date, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def new_id() -> str:
    return uuid4().hex


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class DailyUsage(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        CheckConstraint("minutes >= 0", name="ck_daily_usage_minutes_nonnegative"),
    )

    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[date] = mapped_column(Date, primary_key=True, default=lambda: utc_now().date())
    minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        CheckConstraint("status IN ('parsing', 'ready', 'failed')", name="ck_resumes_status"),
        Index("ix_resumes_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="parsing")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now,
        server_default=func.now(),
    )
    profile_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class InterviewSession(Base):
    __tablename__ = "sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('planning', 'ready', 'failed', 'live', 'completed')",
            name="ck_sessions_status",
        ),
        CheckConstraint("mode = 'resume'", name="ck_sessions_mode"),
        CheckConstraint("duration_min > 0", name="ck_sessions_duration_positive"),
        Index("ix_sessions_user_created", "user_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("resumes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    mode: Mapped[str] = mapped_column(String(16), nullable=False, default="resume", server_default="resume")
    level: Mapped[str] = mapped_column(String(24), nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="planning")
    plan: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    profile_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    live_state: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_sec_actual: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class Turn(Base):
    __tablename__ = "turns"
    __table_args__ = (
        CheckConstraint("role IN ('ai', 'user')", name="ck_turns_role"),
        UniqueConstraint("session_id", "idx", name="uq_turns_session_idx"),
        Index("ix_turns_session_created", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(8), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    interrupted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class Evaluation(Base):
    __tablename__ = "evaluations"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_idx", name="uq_evaluations_session_turn"),
        CheckConstraint(
            "correctness IS NULL OR correctness BETWEEN 0 AND 1",
            name="ck_evaluations_correctness_range",
        ),
        CheckConstraint("depth IS NULL OR depth BETWEEN 0 AND 1", name="ck_evaluations_depth_range"),
        CheckConstraint(
            "communication IS NULL OR communication BETWEEN 0 AND 1",
            name="ck_evaluations_communication_range",
        ),
        CheckConstraint("quality IS NULL OR quality BETWEEN 0 AND 1", name="ck_evaluations_quality_range"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    turn_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False)
    scored: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    correctness: Mapped[float | None] = mapped_column(Float, nullable=True)
    depth: Mapped[float | None] = mapped_column(Float, nullable=True)
    communication: Mapped[float | None] = mapped_column(Float, nullable=True)
    quality: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_quality: Mapped[str | None] = mapped_column(String(16), nullable=True)
    goals_covered: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    missed_points: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("status IN ('pending', 'ready', 'failed')", name="ck_reports_status"),
    )

    session_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sessions.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now,
        server_default=func.now(),
    )
