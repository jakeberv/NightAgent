"""Bounded image estimators train only supplied pixels and save portable state."""
import subprocess
import sys

import joblib
import numpy as np
import pytest
from sklearn.base import clone

from tests.test_problem import profile


def image_adapter(model):
    from study.problem import ProblemSpec
    from study.tasks import get_adapter
    value = profile()
    value['search_space']['models'] = [model]
    return get_adapter(ProblemSpec.from_dict(value))


@pytest.mark.parametrize('model', ['torch_mlp', 'torch_cnn'])
def test_image_registry_requires_raw_pixels_and_bounded_parameters(model):
    adapter = image_adapter(model)
    assert adapter.reference_config['preprocessing'] == 'none'
    pipeline = adapter.build_pipeline(adapter.reference_config, seed=3)
    assert clone(pipeline).get_params()['classifier__random_state'] == 3
    for params in ({'epochs': 11}, {'batch_size': 0}, {'learning_rate': .5}, {'weight_decay': -1}):
        with pytest.raises(ValueError):
            adapter.validate_config({'model': model, 'preprocessing': 'none', 'params': params})
    with pytest.raises(ValueError):
        adapter.validate_config({'model': model, 'preprocessing': 'standard', 'params': {}})
    with pytest.raises(ValueError):
        adapter.validate_config({'model': model, 'preprocessing': 'none', 'params': {'device': 'mps'}})


def test_image_models_are_classification_only():
    from study.problem import ProblemSpec
    value = profile('tabular_regression', 'rmse')
    value['search_space']['models'] = ['torch_mlp']
    with pytest.raises(ValueError):
        ProblemSpec.from_dict(value)


def test_image_search_space_rejects_scaling_without_a_raw_pixel_choice():
    from study.problem import ProblemSpec
    value = profile()
    value['search_space'].update(models=['torch_cnn'], preprocessing=['standard'])
    with pytest.raises(ValueError, match='preprocessing'):
        ProblemSpec.from_dict(value)


def test_unfitted_prediction_reports_sklearn_not_fitted():
    from sklearn.exceptions import NotFittedError
    from study.torch_models import TorchImageClassifier
    with pytest.raises(NotFittedError):
        TorchImageClassifier().predict(np.zeros((2, 784)))


@pytest.mark.parametrize('settings', [{'epochs': 0}, {'hidden_width': 1024}, {'architecture': 'cnn', 'channels': 64}, {'learning_rate': float('nan')}, {'batch_size': True}])
def test_direct_estimator_cannot_bypass_training_bounds(settings, pixels):
    from study.torch_models import TorchImageClassifier
    with pytest.raises(ValueError):
        TorchImageClassifier(**settings).fit(*pixels)


def test_registry_and_constructor_leave_torch_unimported():
    result = subprocess.run([sys.executable, '-c',
        "from tests.test_torch_models import image_adapter; import sys; "
        "a=image_adapter('torch_cnn'); a.build_pipeline(a.reference_config, seed=3); "
        "assert 'torch' not in sys.modules"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.fixture
def torch_cpu():
    torch = pytest.importorskip('torch')
    old = torch.get_num_threads()
    torch.set_num_threads(1)
    yield torch
    torch.set_num_threads(old)


@pytest.fixture
def pixels():
    rng = np.random.default_rng(9)
    labels = np.repeat(['dark', 'light'], 32)
    X = rng.integers(0, 12, size=(64, 784)).astype(np.float32)
    X[32:] += 240
    return X, labels


@pytest.mark.parametrize('model', ['torch_mlp', 'torch_cnn'])
def test_train_predict_probabilities_and_portable_roundtrip(model, pixels, torch_cpu, tmp_path):
    X, y = pixels
    adapter = image_adapter(model)
    config = {'model': model, 'preprocessing': 'none', 'params': {'epochs': 3, 'batch_size': 64, 'learning_rate': .01}}
    pipeline = adapter.build_pipeline(config, seed=7).fit(X, y)
    estimator = pipeline.steps[-1][1]
    probabilities = pipeline.predict_proba(X)
    assert probabilities.shape == (64, 2)
    np.testing.assert_allclose(probabilities.sum(axis=1), 1, atol=1e-6)
    assert np.isfinite(probabilities).all()
    np.testing.assert_array_equal(pipeline.classes_, ['dark', 'light'])
    assert (pipeline.predict(X) == y).mean() >= .95
    assert estimator.n_features_in_ == 784
    diagnostics = estimator.training_diagnostics_
    assert diagnostics['device'] == 'cpu'
    assert diagnostics['inference_device'] == 'cpu'
    assert diagnostics['actual_epochs'] == 3
    assert diagnostics['samples'] == 64
    assert diagnostics['fit_seconds'] > 0
    assert len(diagnostics['training_loss']) == 3
    assert np.isfinite(diagnostics['training_loss']).all()
    assert all(isinstance(value, np.ndarray) for value in estimator.state_dict_.values())
    assert not any(isinstance(value, (torch_cpu.Tensor, torch_cpu.nn.Module)) for value in vars(estimator).values())
    # Configured training hardware must not be needed when reading the artifact.
    estimator.set_params(device='mps')
    path = tmp_path / 'model.joblib'
    joblib.dump(pipeline, path)
    restored = joblib.load(path)
    np.testing.assert_array_equal(restored.predict_proba(X), probabilities)


def test_training_reproducible_and_input_untouched(pixels, torch_cpu):
    from study.torch_models import TorchImageClassifier
    X, y = pixels
    original = X.copy()
    options = dict(epochs=2, random_state=12, hidden_width=32)
    first = TorchImageClassifier(**options).fit(X, y)
    second = TorchImageClassifier(**options).fit(X, y)
    np.testing.assert_array_equal(first.predict_proba(X), second.predict_proba(X))
    np.testing.assert_array_equal(X, original)


@pytest.mark.parametrize('bad', [np.ones((8, 4)), np.full((8, 784), -1), np.full((8, 784), 256), np.full((8, 784), np.nan)])
def test_rejects_non_image_or_invalid_pixels(bad, torch_cpu):
    from study.torch_models import TorchImageClassifier
    with pytest.raises(ValueError):
        TorchImageClassifier(epochs=1).fit(bad, np.tile([0, 1], 4))


def test_explicit_unavailable_mps_fails_instead_of_falling_back(monkeypatch, torch_cpu):
    from study.torch_models import resolve_device
    monkeypatch.setattr(torch_cpu.backends.mps, 'is_available', lambda: False)
    assert resolve_device('auto') == 'cpu'
    assert resolve_device('cpu') == 'cpu'
    with pytest.raises(RuntimeError, match='MPS'):
        resolve_device('mps')
    with pytest.raises(ValueError):
        resolve_device('cuda')


def test_cpu_neural_preflight_requires_optional_runtime(monkeypatch):
    from study import torch_models
    def missing():
        raise RuntimeError('PyTorch is required')
    monkeypatch.setattr(torch_models, '_torch', missing)
    with pytest.raises(RuntimeError, match='PyTorch is required'):
        torch_models.resolve_device('cpu')


def test_integral_json_numbers_work_as_integer_training_parameters(pixels, torch_cpu):
    from study.torch_models import TorchImageClassifier
    estimator = TorchImageClassifier(epochs=1.0, batch_size=64.0, hidden_width=32.0)
    estimator.fit(*pixels)
    assert estimator.training_diagnostics_['actual_epochs'] == 1
    assert estimator.predict_proba(pixels[0]).shape == (64, 2)
