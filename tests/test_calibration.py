"""Calibration validates before fitting and persists validation-only outcomes."""
import asyncio
import json
from pathlib import Path

import pytest


def prepared(tmp_path):
    from study.problem import ProblemSpec
    from study.science import prepare_dataset
    problem = ProblemSpec.from_dict({
        'schema_version': 1, 'id': 'calibration-fixture', 'task': 'tabular_classification',
        'brief': 'Classify synthetic examples.', 'dataset': {'format': 'synthetic',
            'n_samples': 120, 'n_features': 4, 'n_classes': 3},
        'evaluation': {'split': {'train': .6, 'validation': .2, 'test': .2, 'seed': 42},
                       'objective': {'metric': 'accuracy', 'direction': 'maximize'}},
        'targets': [], 'search_space': {'preset': 'tabular_classification_small',
                                       'models': ['logistic', 'random_forest']}})
    data = tmp_path / 'data'
    prepare_dataset(data, problem=problem)
    return data


def configs():
    return [{'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': 1, 'max_iter': 100}},
            {'model': 'random_forest', 'preprocessing': 'none', 'params': {'n_estimators': 30}}]


def test_all_configs_must_validate_before_any_fit_or_output(tmp_path, monkeypatch):
    from study import calibrate
    data = prepared(tmp_path)
    async def forbidden(*args, **kwargs):
        pytest.fail('Invalid config list reached a worker')
    monkeypatch.setattr(calibrate, 'run_trial', forbidden)
    bad = configs() + [{'model': 'logistic', 'preprocessing': 'standard', 'params': {'max_iter': 1001}}]
    output = tmp_path / 'output'
    with pytest.raises(ValueError):
        asyncio.run(calibrate.calibrate(data, output, bad, device='cpu'))
    assert not output.exists()


def test_incremental_results_use_balanced_trials_and_continue_after_failure(tmp_path, monkeypatch):
    from study import calibrate
    data, output = prepared(tmp_path), tmp_path / 'output'
    (data / 'test.npz').unlink()  # No calibration operation may open this partition.
    async def worker(data_dir, trial_dir, config, *, seed, timeout, cores):
        checkpoint = json.loads((output / 'calibration.json').read_text())
        assert checkpoint['status'] == 'running'
        assert seed == 42 and 0 < timeout <= 12
        assert 1 <= cores <= 2
        if config['model'] == 'logistic':
            assert checkpoint['results'] == []
            return {'status': 'failed', 'error': 'fixture fit failed', 'elapsed_seconds': .1}
        assert len(checkpoint['results']) == 1
        assert checkpoint['results'][0]['status'] == 'failed'
        return {'status': 'completed', 'score': .75, 'metrics': {'accuracy': .75}, 'elapsed_seconds': .2}
    monkeypatch.setattr(calibrate, 'run_trial', worker)
    result = asyncio.run(calibrate.calibrate(data, output, configs(), device='auto', max_cores=2, trial_timeout=12))
    assert result == json.loads((output / 'calibration.json').read_text())
    assert result['status'] == 'failed' and result['api_calls'] == 0
    assert result['device'] == 'cpu'
    assert [r['status'] for r in result['results']] == ['failed', 'completed']
    assert result['results'][1]['metrics'] == {'accuracy': .75}
    assert all(r['allocated_cores'] >= 1 and r['queue_seconds'] >= 0 for r in result['results'])
    assert not (output / 'test-results.json').exists()


def test_existing_output_is_never_overwritten(tmp_path):
    from study import calibrate
    data, output = prepared(tmp_path), tmp_path / 'output'
    output.mkdir()
    sentinel = output / 'calibration.json'
    sentinel.write_text('original')
    with pytest.raises(ValueError, match='(?i)(exists|immutable|new output)'):
        asyncio.run(calibrate.calibrate(data, output, configs(), device='cpu'))
    assert sentinel.read_text() == 'original'


def test_interruption_preserves_completed_and_cancelled_attempts(tmp_path, monkeypatch):
    from study import calibrate
    data, output = prepared(tmp_path), tmp_path / 'output'
    async def worker(data_dir, trial_dir, config, **kwargs):
        if config['model'] == 'random_forest':
            raise asyncio.CancelledError()
        return {'status': 'completed', 'score': .75, 'metrics': {'accuracy': .75}}
    monkeypatch.setattr(calibrate, 'run_trial', worker)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(calibrate.calibrate(data, output, configs(), device='cpu'))
    saved = json.loads((output / 'calibration.json').read_text())
    assert saved['status'] == 'interrupted'
    assert [r['status'] for r in saved['results']] == ['completed', 'cancelled']


def test_cli_without_credentials_runs_real_validation_worker_and_saves_artifact(tmp_path, monkeypatch):
    from study.calibrate import main
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    data = prepared(tmp_path)
    (data / 'test.npz').unlink()
    path = tmp_path / 'configs.json'
    path.write_text(json.dumps(configs()[:1]))
    output = tmp_path / 'output'
    assert main(['--data', str(data), '--output', str(output), '--configs', str(path),
                 '--device', 'cpu', '--max-cores', '1', '--trial-timeout', '20']) == 0
    saved = json.loads((output / 'calibration.json').read_text())
    assert saved['status'] == 'completed' and saved['api_calls'] == 0
    assert saved['results'][0]['status'] == 'completed'
    assert 0 <= saved['results'][0]['score'] <= 1
    assert Path(saved['results'][0]['artifact']).is_file()


def test_cli_returns_nonzero_when_any_trial_times_out(tmp_path, monkeypatch):
    from study import calibrate
    data = prepared(tmp_path)
    path = tmp_path / 'configs.json'
    path.write_text(json.dumps(configs()))
    async def timeout(*args, **kwargs):
        return {'status': 'timeout', 'error': 'time limit'}
    monkeypatch.setattr(calibrate, 'run_trial', timeout)
    assert calibrate.main(['--data', str(data), '--output', str(tmp_path / 'output'),
                           '--configs', str(path), '--device', 'cpu']) == 1


@pytest.mark.parametrize('settings', [{'trial_timeout': 0}, {'trial_timeout': float('nan')},
                                     {'max_cores': 0}, {'device': 'cuda'}])
def test_bad_execution_settings_fail_before_output(tmp_path, settings):
    from study import calibrate
    data, output = prepared(tmp_path), tmp_path / 'output'
    with pytest.raises(ValueError):
        asyncio.run(calibrate.calibrate(data, output, configs(), **settings))
    assert not output.exists()


def test_changed_training_partition_fails_before_output(tmp_path):
    from study import calibrate
    data, output = prepared(tmp_path), tmp_path / 'output'
    (data / 'train.npz').chmod(0o644)
    (data / 'train.npz').write_bytes(b'changed')
    with pytest.raises(ValueError, match='(?i)(fingerprint|checksum)'):
        asyncio.run(calibrate.calibrate(data, output, configs(), device='cpu'))
    assert not output.exists()


def test_fashion_calibration_examples_fit_the_pilot_bounds():
    from study.problem import load_problem
    from study.tasks import get_adapter
    root = Path(__file__).resolve().parents[1]
    problem = load_problem(root / 'study/problems/fashion-mnist.yaml')
    examples = json.loads((root / 'study/fashion-calibration-configs.json').read_text())
    adapter = get_adapter(problem)
    for config in examples:
        adapter.validate_config(config)
    assert [config['model'] for config in examples] == [
        'logistic', 'random_forest', 'torch_mlp', 'torch_mlp', 'torch_cnn', 'torch_cnn']


@pytest.mark.parametrize('plan', [[], {}, [None]])
def test_invalid_plan_shape_does_not_create_output(tmp_path, plan):
    from study import calibrate
    data, output = prepared(tmp_path), tmp_path / 'output'
    with pytest.raises(ValueError):
        asyncio.run(calibrate.calibrate(data, output, plan, device='cpu'))
    assert not output.exists()
