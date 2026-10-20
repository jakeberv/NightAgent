"""Bounded scientific operations. Role-facing callers receive validation data only.

Like Tutorial 3's physics modules, pipeline construction and schema checking are
ordinary pure Python functions; the subprocess boundary owns resource lifetime.
"""
from __future__ import annotations

import asyncio
import contextlib
import csv
import fcntl
import hashlib
import io
import json
import math
import os
from pathlib import Path
import signal
import sys
import tempfile
import time

import joblib
import jsonschema
import numpy as np
from sklearn.datasets import make_classification
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

MAGIC_FEATURES = ["fLength", "fWidth", "fSize", "fConc", "fConc1", "fAsym", "fM3Long", "fM3Trans", "fAlpha", "fDist"]
PARAMETERS = {
    "logistic": {"C": {"type": "number", "minimum": .001, "maximum": 100}, "max_iter": {"type": "integer", "minimum": 50, "maximum": 1000}},
    "random_forest": {
        "n_estimators": {"type": "integer", "minimum": 10, "maximum": 300},
        "max_depth": {"anyOf": [{"type": "null"}, {"type": "integer", "minimum": 1, "maximum": 30}]},
        "min_samples_leaf": {"type": "integer", "minimum": 1, "maximum": 50},
        "max_features": {"enum": ["sqrt", "log2", 1.0]},
    },
    "histogram_gradient_boosting": {
        "learning_rate": {"type": "number", "minimum": .01, "maximum": .5},
        "max_iter": {"type": "integer", "minimum": 20, "maximum": 400},
        "max_leaf_nodes": {"type": "integer", "minimum": 2, "maximum": 63},
        "max_depth": {"anyOf": [{"type": "null"}, {"type": "integer", "minimum": 1, "maximum": 20}]},
        "l2_regularization": {"type": "number", "minimum": 0, "maximum": 100},
    },
}
ANALYSIS_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["model", "preprocessing", "params"],
    "properties": {"model": {"enum": list(PARAMETERS)}, "preprocessing": {"enum": ["standard", "none"]}, "params": {"type": "object"}},
    "allOf": [
        {"if": {"properties": {"model": {"const": model}}}, "then": {"properties": {"params": {"type": "object", "properties": params, "additionalProperties": False}}}}
        for model, params in PARAMETERS.items()
    ],
}
REFERENCE_CONFIG = {"model": "histogram_gradient_boosting", "preprocessing": "none", "params": {"learning_rate": .1, "max_iter": 200, "max_leaf_nodes": 31, "l2_regularization": 1.0}}
THREAD_ENV = {name: "1" for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS", "BLIS_NUM_THREADS")}


def validate_config(config: dict) -> None:
    """Reject arbitrary code, unknown parameters, nonfinite and unbounded values."""
    try:
        # allow_nan=False additionally closes JSON Schema's NaN comparison loophole.
        json.dumps(config, allow_nan=False)
        jsonschema.Draft202012Validator(ANALYSIS_SCHEMA).validate(config)
    except (ValueError, TypeError, jsonschema.ValidationError) as exc:
        raise ValueError(f"Invalid bounded pipeline configuration: {exc}") from exc


def _validate_seed(seed: int) -> None:
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed < 2**32:
        raise ValueError("seed must be an integer from 0 through 2**32-1")


def build_pipeline(config: dict, *, seed: int) -> Pipeline:
    """Construct an unfitted bounded model; never inspect any dataset here."""
    validate_config(config)
    _validate_seed(seed)
    params = config["params"].copy()
    model = config["model"]
    if model == "logistic":
        classifier = LogisticRegression(**({"C": 1., "max_iter": 300} | params), solver="lbfgs", random_state=seed)
    elif model == "random_forest":
        classifier = RandomForestClassifier(**({"n_estimators": 100, "max_depth": None, "min_samples_leaf": 1, "max_features": "sqrt"} | params), random_state=seed, n_jobs=1)
    else:
        classifier = HistGradientBoostingClassifier(**({"max_iter": 100, "learning_rate": .1, "max_leaf_nodes": 31} | params), random_state=seed, early_stopping=True, validation_fraction=.1, n_iter_no_change=10)
    return Pipeline([("scale", StandardScaler() if config["preprocessing"] == "standard" else "passthrough"), ("classifier", classifier)])


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False, suffix=".tmp") as handle:
        temp = Path(handle.name)
        try:
            json.dump(value, handle, allow_nan=False, sort_keys=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        except BaseException:
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        temp.unlink(missing_ok=True)


def prepare_dataset(output: Path, *, csv_path: Path | None = None, synthetic: bool = False, seed: int = 42, problem=None) -> dict:
    """Prepare a local headerless 10-feature MAGIC CSV, or explicit smoke data.

    Splits are stratified 60/20/20 using fixed-seed index splits. Existing
    prepared directories are immutable: reuse requires identical source/seed
    and intact partition fingerprints. No network download is performed.
    """
    if problem is not None:
        if csv_path is not None or synthetic:
            raise ValueError('problem profile cannot be combined with legacy data arguments')
        return _prepare_problem_dataset(output, problem)
    _validate_seed(seed)
    output = Path(output)
    if synthetic == (csv_path is not None):
        raise ValueError("Choose exactly one of csv_path or synthetic=True")
    if synthetic:
        X, y = make_classification(n_samples=1000, n_features=10, n_informative=7, n_redundant=2, flip_y=0, weights=[.5, .5], random_state=seed)
        source_hash = hashlib.sha256(X.tobytes() + y.tobytes()).hexdigest()
        dataset, features, positive = "synthetic_smoke", [f"feature_{i:02d}" for i in range(1, 11)], "synthetic class 1"
    else:
        raw = Path(csv_path).read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
        try:
            if not rows or any(len(row) != 11 or row[-1].strip() not in ("g", "h") for row in rows):
                raise ValueError("Expected ten numerical columns followed by g or h")
            X = np.asarray([[float(cell) for cell in row[:10]] for row in rows], dtype=np.float64)
            y = np.asarray([int(row[-1].strip() == "g") for row in rows], dtype=np.int64)
        except (ValueError, TypeError) as exc:
            raise ValueError("Invalid headerless MAGIC CSV: " + str(exc)) from exc
        dataset, features, positive = "MAGIC", MAGIC_FEATURES.copy(), "gamma (g)"
    if not np.isfinite(X).all() or len(np.unique(y)) != 2:
        raise ValueError("Dataset must contain finite features and both classes")
    identity = {"dataset": dataset, "source_sha256": source_hash, "seed": seed}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if output.exists() and any(output.iterdir()):
        try:
            previous = json.loads((output / "manifest.json").read_text())
            if previous["data_fingerprint"] != fingerprint or any(_hash_file(output / f"{name}.npz") != part["sha256"] for name, part in previous["partitions"].items()):
                raise ValueError("prepared data differs")
            return previous
        except (OSError, KeyError, ValueError) as exc:
            raise ValueError("Prepared dataset is immutable; use a new output directory") from exc
    try:
        train, holdout = train_test_split(np.arange(len(y)), test_size=.4, random_state=seed, stratify=y)
        validation, test = train_test_split(holdout, test_size=.5, random_state=seed, stratify=y[holdout])
    except ValueError as exc:
        raise ValueError("Dataset is too small for stratified 60/20/20 splitting") from exc
    output.mkdir(parents=True, exist_ok=True)
    partitions = {}
    for name, indices in (("train", train), ("validation", validation), ("test", test)):
        destination = output / f"{name}.npz"
        with tempfile.NamedTemporaryFile(dir=output, delete=False) as handle:
            temp = Path(handle.name)
            np.savez(handle, X=X[indices], y=y[indices], row_ids=indices)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, destination)
        destination.chmod(0o444)
        partitions[name] = {"rows": len(indices), "positive_rows": int(y[indices].sum()), "sha256": _hash_file(destination)}
    manifest = identity | {"data_fingerprint": fingerprint, "feature_names": features, "positive_class": positive, "split_protocol": "stratified 60/20/20; sklearn train_test_split indices; holdout=.4 then .5; same seed at both stages", "partitions": partitions}
    _atomic_json(output / "manifest.json", manifest)
    return manifest


def load_problem_data(problem):
    """Load and validate numeric local data without fitting any estimator."""
    from sklearn.datasets import make_regression
    ds = problem.dataset
    seed = problem.to_dict()['evaluation']['split']['seed']
    test_data = None
    if ds['format'] == 'synthetic':
        if problem.task == 'tabular_classification':
            classes = ds['n_classes']
            features = ds['n_features']
            informative = min(features, max(2, math.ceil(math.log2(classes)) + 1))
            X, y = make_classification(n_samples=ds['n_samples'], n_features=features, n_classes=classes, n_clusters_per_class=1, n_informative=informative, n_redundant=0, flip_y=min(ds.get('noise', 0), 1), random_state=seed)
        else:
            X, y = make_regression(n_samples=ds['n_samples'], n_features=ds['n_features'], n_informative=ds['n_features'], noise=ds.get('noise', 10), random_state=seed)
        features = [f'feature_{i:02d}' for i in range(X.shape[1])]
        source_hash = hashlib.sha256(X.tobytes() + y.tobytes()).hexdigest()
    elif ds['format'] == 'csv':
        raw = Path(ds['path']).read_bytes()
        source_hash = hashlib.sha256(raw).hexdigest()
        rows = list(csv.reader(io.StringIO(raw.decode('utf-8-sig'))))
        if not rows:
            raise ValueError('CSV dataset is empty')
        columns = rows.pop(0) if ds['header'] else ds['columns']
        if len(set(columns)) != len(columns) or any(not name for name in columns):
            raise ValueError('CSV column names must be distinct and nonempty')
        if 'columns' in ds and ds['header'] and ds['columns'] != columns:
            raise ValueError('CSV header differs from declared columns')
        if ds['target_column'] not in columns or any(len(row) != len(columns) for row in rows):
            raise ValueError('CSV target missing or row width differs from declared columns')
        excluded = ds.get('exclude_columns', [])
        if not set(excluded) <= set(columns) or ds['target_column'] in excluded:
            raise ValueError('CSV excluded columns must exist and cannot include target')
        features = ds.get('feature_columns', [name for name in columns if name != ds['target_column'] and name not in excluded])
        if not features or not set(features) <= set(columns) or set(features) & set(excluded):
            raise ValueError('CSV feature selection is empty, missing, or excluded')
        try:
            X = np.asarray([[float(row[columns.index(name)]) for name in features] for row in rows], dtype=np.float64)
            labels = [row[columns.index(ds['target_column'])].strip() for row in rows]
            if any(not label for label in labels):
                raise ValueError('missing target')
            if problem.task == 'tabular_regression' or isinstance(ds.get('positive_class'), (int, float)):
                y = np.asarray(labels, dtype=np.float64)
            else:
                # Preserve string labels rather than silently recoding the positive class.
                y = np.asarray(labels)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'CSV needs numeric finite features and valid targets: {exc}') from exc
    else:
        source_hash = _hash_file(Path(ds['path']))
        try:
            with np.load(ds['path'], allow_pickle=False) as source:
                X, y = source[ds['feature_array']], source[ds['target_array']]
                if 'test_feature_array' in ds:
                    test_data = (source[ds['test_feature_array']], source[ds['test_target_array']])
        except (ValueError, KeyError, OSError) as exc:
            raise ValueError(f'Invalid safe NPZ arrays: {exc}') from exc
        if ds.get('flatten'):
            if X.ndim < 2:
                raise ValueError('flatten requires a sample dimension and feature dimensions')
            original_shape = X.shape[1:]
            X = X.reshape(len(X), -1)
            if test_data is not None:
                tx, ty = test_data
                if tx.shape[1:] != original_shape:
                    raise ValueError('official test feature shape differs from training')
                test_data = (tx.reshape(len(tx), -1), ty)
        features = [f'feature_{i:04d}' for i in range(X.shape[1])] if X.ndim == 2 else []
    def validate(X, y, *, name):
        if X.ndim != 2 or not X.shape[1] or len(X) < 2 or X.dtype.kind not in 'fiu' or not np.isfinite(X).all():
            raise ValueError(f'{name} features must be a nonempty finite numeric 2D matrix; declare flatten for images')
        if y.ndim != 1 or len(y) != len(X) or y.dtype.kind not in 'fiuUS' or any(str(label).strip() == '' for label in y):
            raise ValueError(f'{name} target must be a nonempty one-dimensional numeric/string array')
        if y.dtype.kind in 'fiu' and not np.isfinite(y).all():
            raise ValueError(f'{name} target must be finite')
        if problem.task == 'tabular_regression':
            if y.dtype.kind not in 'fiu':
                raise ValueError('regression targets must be numeric')
        else:
            from sklearn.utils.multiclass import type_of_target
            if y.dtype.kind == 'S' or type_of_target(y) not in ('binary', 'multiclass'):
                raise ValueError('classification targets must be categorical integer or Unicode string labels; nonintegral floats and byte strings are unsupported')
            if len(np.unique(y)) < 2:
                raise ValueError('classification needs at least two classes per partition')
        return np.asarray(X, dtype=np.float64), y
    X, y = validate(X, y, name='source')
    if test_data is not None:
        test_data = validate(*test_data, name='official test')
        if test_data[0].shape[1] != X.shape[1]:
            raise ValueError('official test feature count differs from training')
        if problem.task == 'tabular_classification' and not set(test_data[1].tolist()) <= set(y.tolist()):
            raise ValueError('official test contains classes absent from training')
    metric_names = [problem.objective['metric'], *problem.to_dict()['evaluation']['additional_metrics']]
    if 'roc_auc' in metric_names and (len(np.unique(y)) != 2 or problem.dataset['positive_class'] not in y):
        raise ValueError('binary roc_auc requires exactly two classes including positive_class')
    return X, y, test_data, features, source_hash


def _prepare_problem_dataset(output, problem):
    from study.problem import assert_problem_matches
    from study.tasks import get_adapter
    output = Path(output)
    X, y, official_test, features, source_hash = load_problem_data(problem)
    split = problem.to_dict()['evaluation']['split']
    seed = split['seed']
    adapter = get_adapter(problem)
    identity = {'dataset': problem.id, 'source_sha256': source_hash, 'seed': seed, 'problem_hash': problem.fingerprint, 'adapter': {'id': adapter.id, 'version': adapter.version}}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    if output.exists() and any(output.iterdir()):
        try:
            previous = json.loads((output / 'manifest.json').read_text())
            assert_problem_matches(output, problem)
            if previous['data_fingerprint'] != fingerprint:
                raise ValueError('source fingerprint changed')
            return previous
        except (OSError, KeyError, ValueError) as exc:
            raise ValueError('Prepared dataset is immutable; use a new output directory') from exc
    stratify = y if problem.task == 'tabular_classification' else None
    try:
        if official_test is None:
            train, holdout = train_test_split(np.arange(len(y)), test_size=split['validation']+split['test'], random_state=seed, stratify=stratify)
            validation, test = train_test_split(holdout, test_size=split['test']/(split['validation']+split['test']), random_state=seed, stratify=y[holdout] if stratify is not None else None)
            parts = {'train': (X[train], y[train], train), 'validation': (X[validation], y[validation], validation), 'test': (X[test], y[test], test)}
        else:
            train, validation = train_test_split(np.arange(len(y)), test_size=split['validation'], random_state=seed, stratify=stratify)
            tx, ty = official_test
            parts = {'train': (X[train], y[train], train), 'validation': (X[validation], y[validation], validation), 'test': (tx, ty, np.arange(len(ty))+len(y))}
        if problem.task == 'tabular_classification' and any(set(part[1].tolist()) != set(y.tolist()) for part in parts.values()):
            raise ValueError('each classification partition must contain all classes')
    except ValueError as exc:
        raise ValueError(f'Dataset is too small or classes invalid for declared split: {exc}') from exc
    output.mkdir(parents=True, exist_ok=True)
    partitions = {}
    for name, (px, py, ids) in parts.items():
        destination = output / f'{name}.npz'
        with tempfile.NamedTemporaryFile(dir=output, delete=False) as handle:
            temporary = Path(handle.name)
            np.savez(handle, X=px, y=py, row_ids=ids)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        destination.chmod(0o444)
        partitions[name] = {'rows': len(py), 'sha256': _hash_file(destination)}
    manifest = identity | {'problem': problem.to_dict(), 'data_fingerprint': fingerprint, 'feature_names': features, 'split_protocol': split, 'partitions': partitions}
    _atomic_json(output / 'manifest.json', manifest)
    return manifest


def project_info(data_dir: Path) -> dict:
    """Expose only the fixed scientific brief and permitted training feedback."""
    from study.problem import problem_from_data
    from study.tasks import get_adapter
    problem = problem_from_data(data_dir)
    if problem is not None:
        return get_adapter(problem).describe(data_dir)
    manifest = json.loads((Path(data_dir) / "manifest.json").read_text())
    return {"dataset": manifest["dataset"], "feature_names": manifest["feature_names"], "positive_class": manifest["positive_class"], "counts": {name: manifest["partitions"][name]["rows"] for name in ("train", "validation")}, "metric": "validation ROC-AUC", "preprocessing": "Fit on training partition only", "analysis_schema": ANALYSIS_SCHEMA}


def _worker_env(seed: int) -> dict:
    # Construct a whitelist from constants, never copy provider or cloud secrets.
    return {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONHASHSEED": str(seed), "LOKY_MAX_CPU_COUNT": "1", **THREAD_ENV}


async def _kill_group(process) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(process.pid, signal.SIGKILL)
    await process.wait()


async def run_trial(data_dir: Path, trial_dir: Path, config: dict, *, seed: int, timeout: float) -> dict:
    """Run one bounded worker with train/validation paths, then verify its output."""
    started = time.monotonic()
    process = None
    spawn_task = None
    trial_dir = Path(trial_dir).resolve()
    data_dir = Path(data_dir).resolve()
    artifact = trial_dir / "model.joblib"
    result = None
    try:
        from study.problem import problem_from_data, validate_metric_value
        from study.tasks import get_adapter, worker_problem
        problem = problem_from_data(data_dir)
        adapter = get_adapter(problem) if problem is not None else None
        (adapter.validate_config if adapter else validate_config)(config)
        _validate_seed(seed)
        if not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")
        trial_dir.mkdir(parents=True, exist_ok=False)
        manifest = json.loads((data_dir / "manifest.json").read_text())
        for name in ("train", "validation"):
            if _hash_file(data_dir / f"{name}.npz") != manifest["partitions"][name]["sha256"]:
                raise ValueError(f"{name} partition fingerprint mismatch")
        request = {"train_path": str(data_dir / "train.npz"), "validation_path": str(data_dir / "validation.npz"), "artifact_path": str(artifact), "config": config, "seed": seed, "metadata": {"data_fingerprint": manifest["data_fingerprint"], "train_sha256": manifest["partitions"]["train"]["sha256"], "validation_sha256": manifest["partitions"]["validation"]["sha256"]}}
        if problem is not None:
            request['problem'] = worker_problem(problem)
            request['metadata']['problem_hash'] = problem.fingerprint
        remaining = timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise asyncio.TimeoutError()
        spawn_task = asyncio.create_task(asyncio.create_subprocess_exec(sys.executable, "-m", "study.worker", cwd=Path(__file__).resolve().parent.parent, env=_worker_env(seed), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, start_new_session=True))
        # Shield creation so cancellation cannot lose a child before its handle
        # is assigned; cleanup retrieves that handle and kills the whole group.
        process = await asyncio.wait_for(asyncio.shield(spawn_task), timeout=remaining)
        stdout, stderr = await asyncio.wait_for(process.communicate(json.dumps(request, allow_nan=False).encode()), timeout=max(.000001, timeout - (time.monotonic() - started)))
        if process.returncode != 0:
            raise ValueError(f"worker failed ({process.returncode}): {stderr.decode(errors='replace')[-1000:]}")
        response = json.loads(stdout)
        if response.get("status") != "completed":
            raise ValueError(response.get("error", "worker did not complete"))
        if problem is not None:
            metrics = response['metrics']
            expected = {problem.objective['metric'], *problem.to_dict()['evaluation']['additional_metrics']}
            if not isinstance(metrics, dict) or set(metrics) != expected:
                raise ValueError('invalid worker metrics')
            for metric, value in metrics.items():
                validate_metric_value(metric, value)
            score = response['score']
            if score != metrics[problem.objective['metric']]:
                raise ValueError('worker score differs from configured objective')
        else:
            score = response['validation_auc']
            if isinstance(score, bool) or not isinstance(score, (float, int)) or not math.isfinite(score) or not 0 <= score <= 1:
                raise ValueError('invalid worker validation AUC')
        artifact_hash = _hash_file(artifact)
        if artifact_hash != response["artifact_hash"]:
            raise ValueError("artifact hash mismatch")
        if time.monotonic() - started >= timeout:
            raise asyncio.TimeoutError()
        result = {'status': 'completed', 'artifact': str(artifact), 'artifact_hash': artifact_hash, 'config': config, 'seed': seed}
        if problem is not None:
            result.update(metrics=metrics, score=score)
            if problem.objective['metric'] == 'roc_auc':
                result['validation_auc'] = score
        else:
            result['validation_auc'] = score
    except asyncio.CancelledError:
        if process is None and spawn_task is not None:
            process = await asyncio.shield(spawn_task)
        if process is not None:
            await asyncio.shield(_kill_group(process))
        artifact.unlink(missing_ok=True)
        raise
    except asyncio.TimeoutError:
        if process is None and spawn_task is not None:
            process = await asyncio.shield(spawn_task)
        if process is not None:
            await _kill_group(process)
        artifact.unlink(missing_ok=True)
        result = {"status": "timeout", "error": "trial exceeded wall-time allowance"}
    except Exception as exc:
        if process is not None and process.returncode is None:
            await _kill_group(process)
        # Avoid deleting an artifact belonging to a previously existing directory.
        result = {"status": "failed", "error": str(exc)[:2000]}
    result["elapsed_seconds"] = time.monotonic() - started
    if trial_dir.is_dir() and not (trial_dir / "result.json").exists():
        _atomic_json(trial_dir / "result.json", result)
    return result


def evaluate_selected(data_dir: Path, run_dir: Path, selections: dict[str, dict]) -> dict:
    """Evaluate unique artifacts once, durably reserving before touching labels.

    A reservation left by a crash is uncertain and is never retried. This is
    deliberately at-most-once: no filesystem protocol can guarantee exactly
    once after a crash between scoring and persisting its result.
    """
    data_dir, run_dir = Path(data_dir), Path(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)
    cache_path = run_dir / "test-evaluation-cache.json"
    with (run_dir / ".test-evaluation.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {"version": 1, "artifacts": {}}
        results = {}
        for label, selection in selections.items():
            if selection is None:
                continue
            digest = selection["artifact_hash"]
            if digest in cache["artifacts"]:
                stored = cache["artifacts"][digest]
                if stored["status"] == "in_progress":
                    stored = {"artifact_hash": digest, "status": "uncertain", "error": "prior evaluation was interrupted; never repeated"}
                    cache["artifacts"][digest] = stored
                    _atomic_json(cache_path, cache)
                results[label] = stored
                continue
            cache["artifacts"][digest] = {"artifact_hash": digest, "status": "in_progress"}
            _atomic_json(cache_path, cache)
            try:
                artifact = Path(selection["artifact"])
                if _hash_file(artifact) != digest:
                    raise ValueError("selected artifact hash mismatch")
                manifest = json.loads((data_dir / "manifest.json").read_text())
                if _hash_file(data_dir / "test.npz") != manifest["partitions"]["test"]["sha256"]:
                    raise ValueError("held-out partition hash mismatch")
                bundle = joblib.load(artifact)
                if bundle["metadata"]["data_fingerprint"] != manifest["data_fingerprint"]:
                    raise ValueError("artifact dataset fingerprint mismatch")
                from study.problem import problem_from_data
                from study.tasks import get_adapter
                problem = problem_from_data(data_dir)
                if problem is not None and bundle['metadata'].get('problem_hash') != problem.fingerprint:
                    raise ValueError('artifact problem fingerprint mismatch')
                with np.load(data_dir / 'test.npz', allow_pickle=False) as data, threadpool_limits(limits=1):
                    if problem is None:
                        score = float(roc_auc_score(data['y'], bundle['pipeline'].predict_proba(data['X'])[:, 1]))
                        result = {'artifact_hash': digest, 'status': 'completed', 'test_auc': score}
                    else:
                        metrics = get_adapter(problem).metrics(bundle['pipeline'], data['X'], data['y'])
                        result = {'artifact_hash': digest, 'status': 'completed', 'metrics': metrics, 'score': metrics[problem.objective['metric']]}
                        if problem.objective['metric'] == 'roc_auc':
                            result['test_auc'] = result['score']
            except Exception as exc:
                result = {"artifact_hash": digest, "status": "failed", "error": str(exc)[:2000]}
            cache["artifacts"][digest] = result
            _atomic_json(cache_path, cache)
            results[label] = result
        _atomic_json(run_dir / "test-results.json", {"selections": results, "artifacts": cache["artifacts"]})
        return results


async def fixed_reference(data_dir: Path, output_dir: Path, *, seed: int, timeout: float) -> dict:
    """A frozen task-difficulty reference, scheduled outside all conditions."""
    from study.problem import problem_from_data
    from study.tasks import get_adapter
    problem = problem_from_data(data_dir)
    config = get_adapter(problem).reference_config if problem is not None else json.loads(json.dumps(REFERENCE_CONFIG))
    return await run_trial(data_dir, output_dir, config, seed=seed, timeout=timeout)
