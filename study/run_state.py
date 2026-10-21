"""Mutable budgets and measured observations owned by one run."""
from dataclasses import dataclass, field
from typing import Callable

from .config import StudyConfig
from .events import Accounting
from .problem import ProblemSpec
from .run_context import capacity_estimate, target_status
from .selection import initial_summary


class StopRun(Exception):
    """A harness safeguard ended the search normally."""


@dataclass
class RunState:
    config: StudyConfig
    problem: ProblemSpec
    clock: Callable[[], float]
    data_fingerprint: str | None = None
    accounting: Accounting = field(default_factory=Accounting)
    history: list[dict] = field(default_factory=list)
    call_durations: dict[str, list[float]] = field(default_factory=dict)
    model_seconds: float = 0.0
    feedback: dict | None = None
    reflection: dict | None = None
    initial_framing: dict | None = None
    summary: dict = field(init=False)
    started: float = field(init=False)

    def __post_init__(self):
        self.summary = initial_summary(self.config, self.problem, self.data_fingerprint)
        self.started = self.clock()

    def remaining(self):
        return self.started + self.config.allowance_seconds - self.clock()

    def check(self):
        if not self.accounting.cost_complete and not self.config.allow_unknown_cost:
            raise StopRun('unknown_cost')
        if self.remaining() <= 0:
            raise StopRun('deadline')
        if self.accounting.known_cost >= self.config.dollar_cap:
            raise StopRun('dollar_cap')
        if self.summary['trials'] >= self.config.trial_cap:
            raise StopRun('trial_cap')

    def targets(self):
        return target_status(self.problem.targets, self.problem.objective,
                             self.summary['best'], self.summary['target_selections'])

    def capacity(self, role, framing=False, phase_completed=False):
        return capacity_estimate(self.config, attempted=self.summary['trials'],
            remaining=self.remaining(), history=self.history, call_durations=self.call_durations,
            role=role, framing=framing, phase_completed=phase_completed)
