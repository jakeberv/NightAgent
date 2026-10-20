"""Deadline regressions use a controlled clock, with no network or real waits."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from study import controller
from study.config import StudyConfig
from study.fake import FakeModel


def timed_run(tmp_path, monkeypatch, *, condition, allowance, call_times, fit_times,
              fail_call=None):
    clock = [100.0]
    monkeypatch.setattr(controller, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    calls, fits = iter(call_times), iter(fit_times)

    class Model(FakeModel):
        count = 0

        async def complete(self, messages, tools, *, timeout):
            self.count += 1
            clock[0] += next(calls)
            if self.count == fail_call:
                raise TimeoutError('Provider did not return usage before deadline')
            return await super().complete(messages, tools, timeout=timeout)

    async def fit(data, output, config, *, seed, timeout):
        clock[0] += next(fits)
        return {'status': 'completed', 'score': .96, 'metrics': {'roc_auc': .96},
                'artifact': 'fake.joblib', 'artifact_hash': str(output)}

    result = asyncio.run(controller.run_one(
        StudyConfig(condition=condition, allowance_seconds=allowance, trial_cap=10),
        tmp_path, tmp_path / 'run', Model(), trial_runner=fit, project={}))
    events = [json.loads(line) for line in (tmp_path / 'run/events.jsonl').read_text().splitlines()]
    return result, events


def test_review_is_skipped_when_followup_experiment_cannot_fit(tmp_path, monkeypatch):
    result, events = timed_run(tmp_path, monkeypatch, condition='frequent', allowance=20,
                              call_times=[5, 5, 5], fit_times=[5])
    assert result['stop_reason'] == 'deadline'
    assert result['trials'] == 1 and result['best']['trial_id'] == 1
    assert result['accounting']['cost_complete']
    assert result['accounting']['calls'] == 2
    skipped = next(e for e in events if e['type'] == 'model_call_skipped')
    assert skipped['role'] == 'supervisor'
    assert skipped['required_seconds'] > skipped['remaining_seconds']


def test_slow_decision_does_not_start_a_fit_that_no_longer_fits(tmp_path, monkeypatch):
    result, events = timed_run(tmp_path, monkeypatch, condition='researcher_alone', allowance=40,
                              call_times=[5, 28], fit_times=[5, 5])
    assert result['stop_reason'] == 'deadline'
    assert result['trials'] == 1 and result['best']['trial_id'] == 1
    assert result['accounting']['cost_complete']
    assert result['accounting']['calls'] == 2
    assert any(e['type'] == 'trial_skipped' for e in events)
    assert sum(e['type'] == 'trial_started' for e in events) == 1
    assert [e['executed'] for e in events if e['type'] == 'decision_contract'] == [True, False]
    from study.report_analysis import recommendation_uptake
    uptake = recommendation_uptake(events, [], [])
    assert uptake['reused_proposals'] == 0
    assert uptake['skipped_proposals'] == 1


def test_timeout_with_a_valid_model_still_reports_unknown_cost(tmp_path, monkeypatch):
    result, events = timed_run(tmp_path, monkeypatch, condition='researcher_alone', allowance=40,
                              call_times=[5, 30], fit_times=[5], fail_call=2)
    assert result['best']['trial_id'] == 1
    assert result['accounting']['cost_complete'] is False
    assert result['stop_reason'] == 'unknown_cost'


@pytest.mark.parametrize('allow_unknown', [False, True])
def test_cli_checks_accounting_even_for_a_normal_stop(allow_unknown):
    from study.__main__ import require_successful_runs
    summary = {'condition': 'frequent', 'repeat': 0, 'stop_reason': 'deadline',
               'best': {'score': .84}, 'accounting': {'cost_complete': False},
               'config': {'allow_unknown_cost': allow_unknown}}
    if allow_unknown:
        require_successful_runs([summary])
    else:
        with pytest.raises(RuntimeError, match='incomplete cost accounting'):
            require_successful_runs([summary])
