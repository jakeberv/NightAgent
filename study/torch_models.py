"""Optional bounded PyTorch image classifiers with CPU-portable fitted state.

Importing this module or constructing estimators does not import PyTorch. Only
fit, predict, and device resolution require the optional runtime. Images are
784 flattened raw pixel intensities in [0, 255], normalized by a fixed divisor;
there is no fitted preprocessing or internal validation/test partition.
"""
from __future__ import annotations

import time

import jsonschema
import numpy as np
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.utils.multiclass import check_classification_targets
from sklearn.utils.validation import check_array, check_is_fitted, check_X_y


def _torch():
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError('PyTorch is required for torch_mlp and torch_cnn; install the optional torch dependency') from exc
    return torch


def resolve_device(requested='auto'):
    """Resolve a trusted execution choice; never fall back from explicit MPS."""
    if requested not in ('auto', 'cpu', 'mps'):
        raise ValueError('device must be auto, cpu, or mps')
    torch = _torch()
    if requested == 'cpu':
        return 'cpu'
    available = torch.backends.mps.is_available()
    if requested == 'mps' and not available:
        raise RuntimeError('MPS was explicitly requested but is not available')
    return 'mps' if available else 'cpu'


class TorchImageClassifier(ClassifierMixin, BaseEstimator):
    """Fixed-epoch image MLP or two-convolution CNN, with CPU-only inference.

    ``device`` controls training only and is retained for provenance. The live
    network is discarded after fitting; ``state_dict_`` contains NumPy arrays.
    The worker controls CPU thread count outside this estimator.
    """

    def __init__(self, architecture='mlp', hidden_width=64, channels=16,
                 epochs=3, batch_size=128, learning_rate=.001, weight_decay=0.,
                 random_state=0, device='cpu'):
        self.architecture = architecture
        self.hidden_width = hidden_width
        self.channels = channels
        self.epochs = epochs
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.random_state = random_state
        self.device = device

    def _validate_options(self):
        from study.science import _validate_seed
        from study.tasks import TORCH_PARAMETERS
        if self.architecture not in ('mlp', 'cnn'):
            raise ValueError('architecture must be mlp or cnn')
        _validate_seed(self.random_state)
        schema = TORCH_PARAMETERS['torch_' + self.architecture]
        for name, bounds in schema.items():
            value = getattr(self, name)
            if not jsonschema.Draft202012Validator(bounds).is_valid(value) or not np.isfinite(value):
                raise ValueError(f'{name} is outside the bounded image model settings')
            if bounds.get('type') == 'integer':
                # JSON Schema accepts 3.0 as integral; PyTorch dimensions and range require int.
                setattr(self, name, int(value))

    @staticmethod
    def _pixels(X):
        X = check_array(X, dtype=np.float32)
        if X.shape[1] != 784:
            raise ValueError('image models require exactly 784 flattened 28x28 pixel features')
        if np.any(X < 0) or np.any(X > 255):
            raise ValueError('raw image pixels must be in [0, 255]')
        return np.ascontiguousarray(X / np.float32(255.))

    def _network(self, torch, class_count):
        nn = torch.nn
        if self.architecture == 'mlp':
            return nn.Sequential(nn.Linear(784, self.hidden_width), nn.ReLU(),
                                 nn.Linear(self.hidden_width, class_count))
        return nn.Sequential(
            nn.Unflatten(1, (1, 28, 28)),
            nn.Conv2d(1, self.channels, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Conv2d(self.channels, 2 * self.channels, kernel_size=3, padding=1), nn.ReLU(), nn.MaxPool2d(2),
            nn.Flatten(), nn.Linear(2 * self.channels * 7 * 7, class_count),
        )

    def fit(self, X, y):
        started = time.perf_counter()
        self._validate_options()
        X, y = check_X_y(X, y, dtype=np.float32)
        check_classification_targets(y)
        pixels = self._pixels(X)
        classes, labels = np.unique(y, return_inverse=True)
        if len(classes) < 2:
            raise ValueError('classification requires at least two training classes')
        torch = _torch()
        device = resolve_device(self.device)
        torch.manual_seed(self.random_state)
        if device == 'mps':
            torch.mps.manual_seed(self.random_state)
        model = self._network(torch, len(classes)).to(device)
        optimizer = torch.optim.Adam(model.parameters(), lr=self.learning_rate, weight_decay=self.weight_decay)
        criterion = torch.nn.CrossEntropyLoss()
        features = torch.from_numpy(pixels)
        targets = torch.from_numpy(labels.astype(np.int64))
        generator = torch.Generator(device='cpu').manual_seed(self.random_state)
        losses = []
        model.train()
        for _ in range(self.epochs):
            order = torch.randperm(len(labels), generator=generator)
            total = torch.zeros((), device=device)
            for start in range(0, len(labels), self.batch_size):
                indexes = order[start:start + self.batch_size]
                batch = features[indexes].to(device)
                batch_targets = targets[indexes].to(device)
                optimizer.zero_grad(set_to_none=True)
                loss = criterion(model(batch), batch_targets)
                loss.backward()
                optimizer.step()
                # Retain no graph and synchronize only once per epoch.
                total += loss.detach() * len(indexes)
            mean_loss = float(total.cpu().item() / len(labels))
            if not np.isfinite(mean_loss):
                raise RuntimeError('image model training produced non-finite loss')
            losses.append(mean_loss)
        self.classes_ = classes
        self.n_features_in_ = 784
        self.state_dict_ = {name: value.detach().cpu().numpy().copy() for name, value in model.state_dict().items()}
        self.training_diagnostics_ = {
            'training_loss': losses, 'actual_epochs': len(losses),
            'device': device, 'inference_device': 'cpu',
            'fit_seconds': time.perf_counter() - started, 'samples': len(labels),
            'torch_version': torch.__version__, 'pixel_divisor': 255.,
        }
        return self

    def predict_proba(self, X):
        check_is_fitted(self, ['state_dict_', 'classes_', 'n_features_in_'])
        pixels = self._pixels(X)
        torch = _torch()
        model = self._network(torch, len(self.classes_))
        model.load_state_dict({name: torch.from_numpy(value) for name, value in self.state_dict_.items()})
        model.eval()
        probabilities = []
        with torch.inference_mode():
            for start in range(0, len(pixels), self.batch_size):
                batch = torch.from_numpy(pixels[start:start + self.batch_size])
                probabilities.append(torch.softmax(model(batch), dim=1).numpy())
        return np.concatenate(probabilities)

    def predict(self, X):
        probabilities = self.predict_proba(X)
        return self.classes_[probabilities.argmax(axis=1)]
