"""Frozen, serializable pilot settings shared across experimental conditions."""
from dataclasses import asdict, dataclass, replace
import math

CONDITIONS = (
    "researcher_alone", "frequent", "periodic", "periodic_reflection",
    "periodic_reflection_literature",
)


@dataclass(frozen=True)
class StudyConfig:
    condition: str = "researcher_alone"
    repeat: int = 0
    model: str = ""
    provider: str = ""
    temperature: float = 0.0
    max_tokens: int = 2048
    allowance_seconds: float = 900
    trial_timeout_seconds: float = 60
    trial_cap: int = 1000
    dollar_cap: float = 20
    # Compatibility defaults only; a resolved ProblemSpec owns scientific targets.
    milestone: float = .93
    stretch: float = .95
    training_seed: int = 42
    history_trials: int = 12
    model_timeout_seconds: float = 90
    model_retries: int = 1
    max_turns_without_trial: int = 8
    review_tool_calls: int = 6
    literature_calls_per_review: int = 3
    literature_timeout_seconds: float = 15
    allow_unknown_cost: bool = False
    max_cores: int | None = None

    def __post_init__(self):
        if self.max_cores is not None:
            from .resources import validate_cores
            validate_cores(self.max_cores)
        if self.condition not in CONDITIONS:
            raise ValueError(f"Unknown condition: {self.condition}")
        for name in ("allowance_seconds", "trial_timeout_seconds", "dollar_cap",
                     "model_timeout_seconds", "literature_timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("max_tokens", "trial_cap", "history_trials", "max_turns_without_trial",
                     "review_tool_calls", "literature_calls_per_review"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        for name in ("repeat", "training_seed", "model_retries"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 0:
                raise ValueError(f"{name} must be a nonnegative integer")
        if not (0 <= self.milestone <= self.stretch <= 1):
            raise ValueError("Require 0 <= milestone <= stretch <= 1")
        if not math.isfinite(self.temperature) or not 0 <= self.temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")
        if type(self.allow_unknown_cost) is not bool:
            raise ValueError("allow_unknown_cost must be boolean")

    def to_dict(self):
        return asdict(self)

    def for_run(self, condition, repeat):
        return replace(self, condition=condition, repeat=repeat,
                       training_seed=self.training_seed + repeat)

    @property
    def review_every(self):
        return 1 if self.condition == "frequent" else (3 if self.condition != "researcher_alone" else None)

    @property
    def reflection(self):
        return self.condition in CONDITIONS[3:]

    @property
    def literature(self):
        return self.condition == CONDITIONS[4]
