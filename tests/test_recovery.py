"""Recovery uses the declared current run, never guesses a policy or problem."""
import json

import pytest

from study.config import StudyConfig
from study.problem import legacy_problem
from study.recovery import recover_run


def interrupted_run(root):
    config = StudyConfig(trial_cap=1).to_dict()
    problem = legacy_problem()
    frozen = {'config': config, 'problem': problem.to_dict(),
              'problem_hash': problem.fingerprint, 'data_fingerprint': 'fixture-data'}
    (root/'resolved-config.json').write_text(json.dumps(frozen))
    (root/'config.json').write_text(json.dumps(config))
    (root/'problem.json').write_text(json.dumps(problem.to_dict()))
    (root/'events.jsonl').write_text(json.dumps({'type': 'run_started', 'elapsed_seconds': 0,
                                               'data_fingerprint': 'fixture-data'})+'\n')
    return frozen


@pytest.mark.parametrize('policy', ['decision_protocol', 'reasoning_policy', 'supervisor_policy'])
def test_recovery_does_not_silently_replace_an_unsupported_frozen_policy(tmp_path, policy):
    frozen = interrupted_run(tmp_path)
    frozen['config'][policy] = 'unsupported-future-policy'
    (tmp_path/'resolved-config.json').write_text(json.dumps(frozen))
    with pytest.raises(ValueError, match=policy):
        recover_run(tmp_path)
    assert not (tmp_path/'summary.json').exists()


def test_recovery_requires_resolved_science_instead_of_inventing_defaults(tmp_path):
    interrupted_run(tmp_path)
    (tmp_path/'resolved-config.json').unlink()
    with pytest.raises(FileNotFoundError, match='resolved-config'):
        recover_run(tmp_path)
    assert not (tmp_path/'summary.json').exists()
