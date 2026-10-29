from dataclasses import dataclass, field
from typing import Any

from common.schemas.live import LiveState
from common.schemas.plan import Plan, PlanThread


@dataclass
class InterviewRuntime:
    plan: Plan
    duration_min: int
    state: LiveState = field(default_factory=LiveState)
    last_missed_points: list[str] = field(default_factory=list)
    exchange: list[tuple[str, str]] = field(default_factory=list)
    started_monotonic: float = 0.0
    opening_pending: bool = True
    seed_pending: bool = True
    low_confidence: bool = False
    repeat_request: bool = False
    silence_check_sent: bool = False
    next_action: str = "seed"
    closing_started: bool = False
    last_question: str = ""
    format_request: bool = False
    allow_hint: bool = False
    writer: Any = None
    tasks: set[Any] = field(default_factory=set)
    evaluation_tasks: set[Any] = field(default_factory=set)
    agent_ref: Any = None

    @property
    def elapsed_sec(self) -> float:
        import time

        return max(0.0, time.monotonic() - self.started_monotonic)

    @property
    def remaining_sec(self) -> float:
        return self.duration_min * 60 - self.elapsed_sec

    @property
    def current_thread(self) -> PlanThread | None:
        if 0 <= self.state.thread_idx < len(self.plan.threads):
            return self.plan.threads[self.state.thread_idx]
        return None

    def thread_remaining_sec(self) -> float:
        thread = self.current_thread
        if thread is None:
            return 0
        return thread.time_budget_sec - (self.elapsed_sec - self.state.thread_started_at_sec)

    def uncovered_goals(self) -> list[str]:
        thread = self.current_thread
        if thread is None:
            return []
        covered = set(self.state.goals_covered.get(thread.id, []))
        return [goal for goal in thread.goals if goal not in covered]

    def thread_should_advance(self) -> bool:
        thread = self.current_thread
        if thread is None:
            return True
        return (
            not self.uncovered_goals()
            or self.state.followups_used >= thread.max_followups
            or self.thread_remaining_sec() <= 0
        )

    def advance(self) -> bool:
        if self.state.thread_idx + 1 >= len(self.plan.threads):
            self.state.thread_idx = len(self.plan.threads)
            return False
        self.state.thread_idx += 1
        self.state.followups_used = 0
        self.state.hints_used_in_thread = 0
        self.state.thread_started_at_sec = self.elapsed_sec
        return True
