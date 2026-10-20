import asyncio
from datetime import datetime, timedelta, timezone
import json

import pytest

from study.config import CONDITIONS, StudyConfig
from study.suite import run_suite


def test_suite_requires_full_equal_allowances_and_reserve_before_any_call(tmp_path):
    called = []
    async def runner(*args, **kwargs):
        called.append(True)
    with pytest.raises(ValueError, match="window"):
        asyncio.run(run_suite(StudyConfig(allowance_seconds=60), tmp_path, tmp_path / "suite",
            repeats=2, deadline=datetime.now(timezone.utc) + timedelta(seconds=100),
            reserve_seconds=20, model_factory=lambda config: None, runner=runner))
    assert called == []


def test_suite_interleaves_all_conditions_with_matched_seeds_and_frozen_manifest(tmp_path):
    configs = []
    async def runner(config, data_dir, run_dir, model):
        configs.append(config)
        run_dir.mkdir(parents=True)
        return {"stop_reason": "trial_cap"}
    directory = tmp_path / "suite"
    asyncio.run(run_suite(StudyConfig(allowance_seconds=1), tmp_path, directory,
        repeats=2, deadline=datetime.now(timezone.utc) + timedelta(seconds=60),
        reserve_seconds=5, model_factory=lambda config: None, runner=runner))
    assert len(configs) == 10
    for repeat in range(2):
        group = [c for c in configs if c.repeat == repeat]
        assert {c.condition for c in group} == set(CONDITIONS)
        assert {c.training_seed for c in group} == {42 + repeat}
        assert {c.allowance_seconds for c in group} == {1}
    manifest = json.loads((directory / "suite.json").read_text())
    assert len(manifest["schedule"]) == 10
    assert manifest["reserve_seconds"] == 5


def test_accounting_does_not_double_count_cached_or_reasoning_tokens():
    from study.events import Accounting
    accounting = Accounting()
    accounting.add({"prompt_tokens": 100, "completion_tokens": 20, "cost": .2,
        "prompt_tokens_details": {"cached_tokens": 50},
        "completion_tokens_details": {"reasoning_tokens": 10}})
    assert accounting.input_tokens + accounting.output_tokens == 120
    assert accounting.cached_tokens == 50
    assert accounting.reasoning_tokens == 10
    accounting.add(None)
    assert accounting.known_cost == .2
    assert not accounting.cost_complete and not accounting.token_usage_complete
