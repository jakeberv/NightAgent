"""Real isolated neural worker contract; CPU execution keeps CI GPU-independent."""
import asyncio
import hashlib

import joblib
import numpy as np
import pytest
from sklearn.metrics import accuracy_score, f1_score

from tests.test_problem import profile


def test_torch_worker_trains_declared_pixels_and_saves_portable_probabilities(tmp_path):
    pytest.importorskip('torch')
    from study.problem import ProblemSpec
    from study.science import prepare_dataset, run_trial

    rng = np.random.default_rng(17)
    labels = np.repeat(['dark', 'light'], 60)
    pixels = rng.integers(0, 12, size=(120, 28, 28), dtype=np.uint8)
    pixels[60:] += 240
    source = tmp_path / 'pixels.npz'
    np.savez(source, pixels=pixels, labels=labels)
    declaration = profile()
    declaration['dataset'] = {'format': 'npz', 'path': str(source),
                              'feature_array': 'pixels', 'target_array': 'labels', 'flatten': True}
    declaration['evaluation']['additional_metrics'] = ['macro_f1']
    declaration['search_space'] = {'preset': 'tabular_classification', 'models': ['torch_mlp'],
                                   'preprocessing': ['none']}
    problem = ProblemSpec.from_dict(declaration)
    data = tmp_path / 'data'
    manifest = prepare_dataset(data, problem=problem)
    # Trial success cannot depend on the held-out partition or original source.
    (data / 'test.npz').unlink()
    source.unlink()
    config = {'model': 'torch_mlp', 'preprocessing': 'none',
              'params': {'hidden_width': 32, 'epochs': 3, 'batch_size': 64, 'learning_rate': .01}}
    result = asyncio.run(run_trial(data, tmp_path / 'trial', config, seed=19, timeout=30, cores=2, device='cpu'))
    assert result['status'] == 'completed', result
    assert result['allocated_cores'] == 2
    assert result['score'] == result['metrics']['accuracy']
    assert set(result['metrics']) == {'accuracy', 'macro_f1'}
    diagnostics = result['fit_diagnostics']
    assert diagnostics['device'] == diagnostics['inference_device'] == 'cpu'
    assert diagnostics['actual_epochs'] == len(diagnostics['training_loss']) == 3
    assert diagnostics['samples'] == manifest['partitions']['train']['rows']
    assert diagnostics['fit_seconds'] > 0
    assert np.isfinite(diagnostics['training_loss']).all()
    assert result['actual_effective_config']['params']['device'] == 'cpu'
    artifact_path = tmp_path / 'trial' / 'model.joblib'
    assert result['artifact_hash'] == hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    artifact = joblib.load(artifact_path)
    assert artifact['metadata']['allocated_cores'] == 2
    assert artifact['metadata']['problem_hash'] == problem.fingerprint
    assert artifact['metadata']['training_diagnostics'] == diagnostics
    pipeline = artifact['pipeline']
    with np.load(data / 'validation.npz') as validation:
        probabilities = pipeline.predict_proba(validation['X'])
        predictions = pipeline.predict(validation['X'])
        np.testing.assert_allclose(probabilities.sum(axis=1), 1, atol=1e-6)
        np.testing.assert_array_equal(pipeline.classes_, ['dark', 'light'])
        assert accuracy_score(validation['y'], predictions) == result['metrics']['accuracy']
        assert f1_score(validation['y'], predictions, average='macro') == result['metrics']['macro_f1']
        # The configured training accelerator is provenance, not an inference requirement.
        pipeline.steps[-1][1].set_params(device='mps')
        portable_path = tmp_path / 'portable.joblib'
        joblib.dump(pipeline, portable_path)
        np.testing.assert_array_equal(joblib.load(portable_path).predict_proba(validation['X']), probabilities)
