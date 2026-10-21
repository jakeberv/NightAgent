"""Frozen, serializable pilot settings shared across experimental conditions."""
from dataclasses import asdict, dataclass, replace
import math

CONDITIONS = (
    "researcher_alone", "frequent", "periodic", "periodic_reflection",
    "periodic_reflection_literature",
)
SUPERVISOR_STRATEGIES = ('standard', 'night_science')
COMPARISONS = ('schedules', 'supervisor_strategies', 'apprentice_interactions')
APPRENTICE_ARMS = (
    ('researcher_alone', 'researcher_alone', True),
    ('frequent', 'frequent', True),
    ('periodic', 'periodic', True),
    ('periodic_reflection', 'periodic_reflection', True),
    ('periodic_reflection_no_memory', 'periodic_reflection', False),
)
APPRENTICE_CONTRASTS = (
    ('researcher_alone', 'frequent'),
    ('frequent', 'periodic'),
    ('periodic', 'periodic_reflection'),
    ('periodic_reflection_no_memory', 'periodic_reflection'),
)


def apprentice_arm(config):
    """Recognize only the declared style/schedule/memory combinations."""
    if config.get('supervisor_strategy') != 'night_science' or type(config.get('lesson_memory')) is not bool:
        return None
    return next((name for name, condition, memory in APPRENTICE_ARMS
                 if config.get('condition') == condition and config['lesson_memory'] == memory), None)


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
    model_start_buffer_seconds: float = 1.0
    deadline_policy: str = 'observed_v1'
    model_retries: int = 1
    max_turns_without_trial: int = 8
    review_tool_calls: int = 6
    literature_calls_per_review: int = 3
    literature_timeout_seconds: float = 15
    allow_unknown_cost: bool = False
    max_cores: int | None = None
    device: str = 'auto'
    decision_protocol: str = "structured_v2"
    reasoning_policy: str = "grounded_v3"
    context_policy: str = "active_advice_v1"
    supervisor_policy: str = "supervision_v2"
    supervisor_strategy: str = "night_science"
    comparison: str = "schedules"
    lesson_memory: bool = True
    memory_limit: int = 6

    def __post_init__(self):
        if self.context_policy != 'active_advice_v1':
            raise ValueError('context_policy must be active_advice_v1')
        if self.deadline_policy != 'observed_v1':
            raise ValueError('deadline_policy must be observed_v1')
        if self.supervisor_policy != "supervision_v2":
            raise ValueError("supervisor_policy must be supervision_v2")
        if self.supervisor_strategy not in SUPERVISOR_STRATEGIES:
            raise ValueError('Unknown supervisor_strategy')
        if self.comparison not in COMPARISONS:
            raise ValueError('Unknown comparison')
        if self.comparison == 'apprentice_interactions' and apprentice_arm(self.to_dict()) is None:
            raise ValueError('Invalid apprentice_interactions arm: use Night Science and the declared schedule/memory settings')
        if self.device not in ('auto', 'cpu', 'mps'):
            raise ValueError('device must be auto, cpu, or mps')
        if self.reasoning_policy != "grounded_v3":
            raise ValueError("reasoning_policy must be grounded_v3")
        if self.decision_protocol not in ("structured_v1", "structured_v2"):
            raise ValueError("decision_protocol must be structured_v2 (structured_v1 is readable historical metadata)")
        if type(self.lesson_memory) is not bool:
            raise ValueError("lesson_memory must be boolean")
        if type(self.memory_limit) is not int or not 1 <= self.memory_limit <= 12:
            raise ValueError("memory_limit must be an integer from 1 to 12")
        if self.max_cores is not None:
            from .resources import validate_cores
            validate_cores(self.max_cores)
        if self.condition not in CONDITIONS:
            raise ValueError(f"Unknown condition: {self.condition}")
        value = self.model_start_buffer_seconds
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise ValueError("model_start_buffer_seconds must be finite and nonnegative")
        for name in ("allowance_seconds", "trial_timeout_seconds", "dollar_cap",
                     "model_timeout_seconds", "literature_timeout_seconds"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive")
        for name in ("max_tokens", "trial_cap", "history_trials", "max_turns_without_trial",
                     "review_tool_calls", "literature_calls_per_review"):
            if type(getattr(self, name)) is not int or getattr(self, name) < 1:
                raise ValueError(f"{name} must be a positive integer")
        if type(self.training_seed) is not int or not 0 <= self.training_seed < 2**32:
            raise ValueError("training_seed must be an integer from 0 through 2**32-1")
        for name in ("repeat", "model_retries"):
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

    def for_run(self, condition, repeat, *, supervisor_strategy=None, lesson_memory=None):
        return replace(self, condition=condition, repeat=repeat,
                       supervisor_strategy=self.supervisor_strategy if supervisor_strategy is None else supervisor_strategy,
                       lesson_memory=self.lesson_memory if lesson_memory is None else lesson_memory,
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


def comparison_arms(config):
    """Freeze the intended arms separately from review cadence and run identity."""
    if config.comparison == 'apprentice_interactions':
        return [{'arm': name, 'condition': condition, 'supervisor_strategy': 'night_science',
                 'lesson_memory': memory} for name, condition, memory in APPRENTICE_ARMS]
    if config.comparison == 'supervisor_strategies':
        return [
            {'arm': 'researcher_alone', 'condition': 'researcher_alone', 'supervisor_strategy': 'night_science'},
            {'arm': 'standard_supervisor', 'condition': 'frequent', 'supervisor_strategy': 'standard'},
            {'arm': 'night_science_supervisor', 'condition': 'frequent', 'supervisor_strategy': 'night_science'},
        ]
    return [{'arm': condition, 'condition': condition, 'supervisor_strategy': config.supervisor_strategy}
            for condition in CONDITIONS]
