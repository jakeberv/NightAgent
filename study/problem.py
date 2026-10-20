"""Strict declarative problem definitions; profiles never supply executable code."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
import re

import yaml

METRICS = {
    'roc_auc': {'task': 'tabular_classification', 'direction': 'maximize', 'minimum': 0, 'maximum': 1},
    'roc_auc_ovr_macro': {'task': 'tabular_classification', 'direction': 'maximize', 'minimum': 0, 'maximum': 1},
    'accuracy': {'task': 'tabular_classification', 'direction': 'maximize', 'minimum': 0, 'maximum': 1},
    'macro_f1': {'task': 'tabular_classification', 'direction': 'maximize', 'minimum': 0, 'maximum': 1},
    'rmse': {'task': 'tabular_regression', 'direction': 'minimize', 'minimum': 0},
    'mae': {'task': 'tabular_regression', 'direction': 'minimize', 'minimum': 0},
    'r2': {'task': 'tabular_regression', 'direction': 'maximize', 'maximum': 1},
}


def _fields(value, allowed, required=(), *, context):
    if not isinstance(value, dict) or any(not isinstance(k, str) for k in value):
        raise ValueError(f'{context} must be an object with string keys')
    if set(value) - set(allowed) or set(required) - set(value):
        raise ValueError(f'{context}: unknown or missing fields: {sorted(set(value)-set(allowed))}, {sorted(set(required)-set(value))}')


def _number(value, *, context, minimum=None, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{context} must be finite numeric')
    if minimum is not None and value < minimum or maximum is not None and value > maximum:
        raise ValueError(f'{context} is outside permitted metric bounds')


def validate_metric_value(metric, value):
    spec = METRICS[metric]
    _number(value, context=metric, minimum=spec.get('minimum'), maximum=spec.get('maximum'))


def _names(value, context):
    if not isinstance(value, list) or not value or any(not isinstance(s, str) or not s for s in value) or len(set(value)) != len(value):
        raise ValueError(f'{context} must be a nonempty list of distinct names')


class ProblemSpec:
    """Validated, resolved value object. All public structured values are copies."""
    def __init__(self, value):
        self._value = copy.deepcopy(value)

    @classmethod
    def from_dict(cls, value, base_dir=Path('.')):
        try:
            json.dumps(value, allow_nan=False)
        except (TypeError, ValueError, OverflowError, RecursionError) as exc:
            raise ValueError('Problem must contain finite JSON values') from exc
        value = copy.deepcopy(value)
        _fields(value, ['schema_version', 'id', 'task', 'brief', 'dataset', 'evaluation', 'targets', 'search_space'], ['schema_version', 'id', 'task', 'brief', 'dataset', 'evaluation', 'targets', 'search_space'], context='problem')
        if type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise ValueError('schema_version must be 1')
        if not isinstance(value['id'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', value['id']):
            raise ValueError('id must be a simple nonempty identifier')
        task = value['task']
        if task not in ('tabular_classification', 'tabular_regression'):
            raise ValueError('unsupported trusted task adapter')
        if not isinstance(value['brief'], str) or not value['brief'].strip():
            raise ValueError('brief must be nonempty text')
        ds = value['dataset']
        _fields(ds, ['format', 'path', 'header', 'columns', 'target_column', 'feature_columns', 'exclude_columns', 'positive_class', 'feature_array', 'target_array', 'test_feature_array', 'test_target_array', 'flatten', 'n_samples', 'n_features', 'n_classes', 'noise'], ['format'], context='dataset')
        fmt = ds['format']
        common = {'format', 'positive_class'}
        if fmt == 'csv':
            allowed = common | {'path', 'header', 'columns', 'target_column', 'feature_columns', 'exclude_columns'}
            if not isinstance(ds.get('header'), bool) or not isinstance(ds.get('target_column'), str) or not ds['target_column']:
                raise ValueError('CSV needs explicit header boolean and target_column name')
            if not ds['header'] and 'columns' not in ds:
                raise ValueError('Headerless CSV needs explicit columns')
            for key in ('columns', 'feature_columns', 'exclude_columns'):
                if key in ds:
                    _names(ds[key], key)
            if 'feature_columns' in ds and ds['target_column'] in ds['feature_columns']:
                raise ValueError('target column cannot be a feature')
        elif fmt == 'npz':
            allowed = common | {'path', 'feature_array', 'target_array', 'test_feature_array', 'test_target_array', 'flatten'}
            for key in ('feature_array', 'target_array'):
                if not isinstance(ds.get(key), str) or not ds[key]:
                    raise ValueError(f'NPZ needs explicit {key}')
            if ('test_feature_array' in ds) != ('test_target_array' in ds):
                raise ValueError('NPZ official test needs both named arrays')
            for key in ('test_feature_array', 'test_target_array'):
                if key in ds and (not isinstance(ds[key], str) or not ds[key]):
                    raise ValueError(f'{key} must be a nonempty name')
            if 'flatten' in ds and not isinstance(ds['flatten'], bool):
                raise ValueError('flatten must be boolean')
            array_names = [ds[k] for k in ('feature_array', 'target_array', 'test_feature_array', 'test_target_array') if k in ds]
            if len(array_names) != len(set(array_names)):
                raise ValueError('NPZ feature/target arrays must have distinct names')
        elif fmt == 'synthetic':
            allowed = common | {'n_samples', 'n_features', 'n_classes', 'noise'}
            for key, default, low, high in (('n_samples', 1000, 30, 100000), ('n_features', 10, 2, 1000), ('n_classes', 2, 2, 100)):
                if key == 'n_classes' and task == 'tabular_regression':
                    if key in ds:
                        raise ValueError('regression has no n_classes')
                    continue
                number = ds.setdefault(key, default)
                if type(number) is not int or not low <= number <= high:
                    raise ValueError(f'{key} must be an integer in [{low},{high}]')
            if 'noise' in ds:
                _number(ds['noise'], context='noise', minimum=0, maximum=1000)
        else:
            raise ValueError('dataset format must be csv, npz, or synthetic')
        if set(ds) - allowed:
            raise ValueError(f'incompatible dataset fields: {sorted(set(ds)-allowed)}')
        if fmt in ('csv', 'npz'):
            if not isinstance(ds.get('path'), str) or not ds['path']:
                raise ValueError('dataset path must be nonempty text')
            ds['path'] = str((Path(base_dir) / ds['path']).resolve())
        if 'positive_class' in ds and (ds['positive_class'] is None or isinstance(ds['positive_class'], (bool, list, dict))):
            raise ValueError('positive_class must be a numeric or string label')
        evaluation = value['evaluation']
        _fields(evaluation, ['split', 'objective', 'additional_metrics'], ['split', 'objective'], context='evaluation')
        objective = evaluation['objective']
        _fields(objective, ['metric', 'direction'], ['metric', 'direction'], context='objective')
        metric = objective['metric']
        if not isinstance(metric, str) or metric not in METRICS or METRICS[metric]['task'] != task or METRICS[metric]['direction'] != objective['direction']:
            raise ValueError('metric/task/direction combination is invalid')
        metrics = evaluation.setdefault('additional_metrics', [])
        if not isinstance(metrics, list) or any(not isinstance(m, str) or m not in METRICS or METRICS[m]['task'] != task for m in metrics) or len(metrics) != len(set(metrics)) or metric in metrics:
            raise ValueError('additional_metrics must be compatible distinct metrics excluding objective')
        if 'roc_auc_ovr_macro' in [metric, *metrics] and 'positive_class' in ds:
            raise ValueError('roc_auc_ovr_macro averages all classes and cannot specify positive_class')
        if 'roc_auc' in [metric, *metrics] and 'positive_class' not in ds:
            raise ValueError('binary roc_auc requires explicit dataset positive_class')
        split = evaluation['split']
        _fields(split, ['train', 'validation', 'test', 'seed', 'method'], ['train', 'validation', 'test'], context='split')
        split.setdefault('seed', 42)
        if type(split['seed']) is not int or not 0 <= split['seed'] < 2**32:
            raise ValueError('split seed must be integer from 0 through 2**32-1')
        official = fmt == 'npz' and 'test_feature_array' in ds
        if official != (split['test'] == 'official'):
            raise ValueError('official test arrays require split.test: official, and vice versa')
        method = 'predefined_test' if official else ('stratified_holdout' if task == 'tabular_classification' else 'random_holdout')
        if split.setdefault('method', method) != method:
            raise ValueError(f'split method must be {method}')
        fractions = [split['train'], split['validation']] + ([] if official else [split['test']])
        for fraction in fractions:
            _number(fraction, context='split fraction', minimum=.000001, maximum=.999999)
        if not math.isclose(sum(fractions), 1, abs_tol=1e-9):
            raise ValueError('split fractions must sum to 1')
        targets = value['targets']
        if not isinstance(targets, list):
            raise ValueError('targets must be a list')
        names = set()
        for target in targets:
            _fields(target, ['name', 'value'], ['name', 'value'], context='target')
            if not isinstance(target['name'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', target['name']) or target['name'] in names or target['name'] == 'best':
                raise ValueError('target names must be distinct simple identifiers')
            names.add(target['name'])
            validate_metric_value(metric, target['value'])
        from study.tasks import validate_search_space
        value['search_space'] = validate_search_space(task, value['search_space'])
        return cls(value)

    def to_dict(self):
        return copy.deepcopy(self._value)

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self._value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()

    @property
    def id(self): return self._value['id']
    @property
    def task(self): return self._value['task']
    @property
    def brief(self): return self._value['brief']
    @property
    def objective(self): return copy.deepcopy(self._value['evaluation']['objective'])
    @property
    def targets(self): return copy.deepcopy(self._value['targets'])
    @property
    def dataset(self): return copy.deepcopy(self._value['dataset'])
    @property
    def search_space(self): return copy.deepcopy(self._value['search_space'])


def _unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate profile key: {key}')
        result[key] = value
    return result


class _UniqueLoader(yaml.SafeLoader):
    pass


def _yaml_mapping(loader, node):
    return _unique_pairs(loader.construct_pairs(node, deep=True))


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _yaml_mapping)


def load_problem(path):
    path = Path(path)
    try:
        raw = path.read_text(encoding='utf-8')
        value = json.loads(raw, object_pairs_hook=_unique_pairs) if path.suffix.lower() == '.json' else yaml.load(raw, Loader=_UniqueLoader)
        return ProblemSpec.from_dict(value, base_dir=path.resolve().parent)
    except (yaml.YAMLError, OSError, TypeError, RecursionError, json.JSONDecodeError) as exc:
        raise ValueError(f'Invalid problem profile {path}: {exc}') from exc


def legacy_problem(milestone=.93, stretch=.95):
    return ProblemSpec.from_dict({'schema_version': 1, 'id': 'legacy-magic', 'task': 'tabular_classification', 'brief': 'Predict gamma versus hadron events from ten numerical telescope features.', 'dataset': {'format': 'synthetic', 'positive_class': 1}, 'evaluation': {'split': {'train': .6, 'validation': .2, 'test': .2, 'seed': 42}, 'objective': {'metric': 'roc_auc', 'direction': 'maximize'}, 'additional_metrics': []}, 'targets': [{'name': 'milestone', 'value': milestone}, {'name': 'stretch', 'value': stretch}], 'search_space': {'preset': 'tabular_classification_small', 'models': ['logistic', 'random_forest', 'histogram_gradient_boosting']}})


def problem_from_data(data_dir):
    path = Path(data_dir) / 'manifest.json'
    if not path.exists():
        return None
    manifest = json.loads(path.read_text())
    if 'problem' not in manifest:
        return None
    problem = ProblemSpec.from_dict(manifest['problem'])
    if problem.fingerprint != manifest.get('problem_hash'):
        raise ValueError('frozen problem fingerprint mismatch')
    return problem


def prepared_data_fingerprint(manifest):
    """Identify scientific inputs independently of the implementation fitting them."""
    identity = {key: manifest[key] for key in (
        'dataset', 'source_sha256', 'seed', 'problem_hash',
        'split_protocol', 'feature_names', 'partitions',
    )}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


def _validate_prepared_data(data_dir, problem):
    from study.science import _hash_file
    data_dir = Path(data_dir)
    frozen = problem_from_data(data_dir)
    if frozen is None or frozen.fingerprint != problem.fingerprint:
        raise ValueError('problem profile differs from frozen prepared problem')
    manifest = json.loads((data_dir / 'manifest.json').read_text())
    split = problem.to_dict()['evaluation']['split']
    if (manifest.get('dataset') != problem.id or manifest.get('seed') != split['seed']
            or manifest.get('split_protocol') != split):
        raise ValueError('prepared dataset identity/split mismatch')
    for name in ('train', 'validation', 'test'):
        try:
            if _hash_file(data_dir / f'{name}.npz') != manifest['partitions'][name]['sha256']:
                raise ValueError(f'{name} partition fingerprint mismatch')
        except (OSError, KeyError) as exc:
            raise ValueError(f'{name} partition fingerprint missing') from exc
    return manifest


def assert_problem_matches(data_dir, problem):
    manifest = _validate_prepared_data(data_dir, problem)
    if 'adapter' in manifest:
        raise ValueError('Prepared metadata needs refreshing; rerun study prepare with the same problem and output directory')
    try:
        if manifest.get('data_fingerprint') != prepared_data_fingerprint(manifest):
            raise ValueError('prepared data fingerprint mismatch')
    except KeyError as exc:
        raise ValueError('prepared data identity missing') from exc
