"""Reviewed task adapters, metric computation, and bounded estimator registry."""
from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import jsonschema
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier, RandomForestRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import accuracy_score, f1_score, mean_absolute_error, mean_squared_error, r2_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

COMMON_PARAMETERS = {
    'random_forest': {'n_estimators': {'type': 'integer', 'minimum': 10, 'maximum': 300}, 'max_depth': {'anyOf': [{'type': 'null'}, {'type': 'integer', 'minimum': 1, 'maximum': 30}]}, 'min_samples_leaf': {'type': 'integer', 'minimum': 1, 'maximum': 50}, 'max_features': {'enum': ['sqrt', 'log2', 1.0]}},
    'histogram_gradient_boosting': {'learning_rate': {'type': 'number', 'minimum': .01, 'maximum': .5}, 'max_iter': {'type': 'integer', 'minimum': 20, 'maximum': 400}, 'max_leaf_nodes': {'type': 'integer', 'minimum': 2, 'maximum': 63}, 'max_depth': {'anyOf': [{'type': 'null'}, {'type': 'integer', 'minimum': 1, 'maximum': 20}]}, 'l2_regularization': {'type': 'number', 'minimum': 0, 'maximum': 100}},
}
DEFAULTS = {
    'logistic': {'C': 1., 'max_iter': 300},
    'ridge': {'alpha': 1.},
    'random_forest': {'n_estimators': 100, 'max_depth': None, 'min_samples_leaf': 1, 'max_features': 'sqrt'},
    'histogram_gradient_boosting': {'learning_rate': .1, 'max_iter': 200, 'max_leaf_nodes': 31, 'max_depth': None, 'l2_regularization': 1.},
}


def _parameters(task):
    parameters = copy.deepcopy(COMMON_PARAMETERS)
    if task == 'tabular_classification':
        return {'logistic': {'C': {'type': 'number', 'minimum': .001, 'maximum': 100}, 'max_iter': {'type': 'integer', 'minimum': 50, 'maximum': 1000}}, **parameters}
    if task == 'tabular_regression':
        return {'ridge': {'alpha': {'type': 'number', 'minimum': .001, 'maximum': 1000}}, **parameters}
    raise ValueError('unknown trusted task')


def _narrow(base, override):
    if not isinstance(override, dict) or set(override) - {'type', 'minimum', 'maximum', 'enum'}:
        raise ValueError('parameter overrides support only narrowing type/bounds/enum')
    if 'anyOf' in base:
        numeric = base['anyOf'][1]
        # Bounds explicitly select the numeric part of a nullable range.
        if not override:
            return copy.deepcopy(base)
        return _narrow(numeric, override)
    result = copy.deepcopy(base)
    if 'type' in override and override['type'] != base.get('type'):
        raise ValueError('parameter override cannot change type')
    for key in ('minimum', 'maximum'):
        if key in override:
            bound = override[key]
            if key not in base or isinstance(bound, bool) or not isinstance(bound, (int, float)) or not math.isfinite(bound):
                raise ValueError('invalid parameter bounds')
            if key == 'minimum' and bound < base[key] or key == 'maximum' and bound > base[key]:
                raise ValueError('parameter override expands trusted bounds')
            result[key] = bound
    if result.get('minimum', -math.inf) > result.get('maximum', math.inf):
        raise ValueError('parameter bounds are empty')
    if 'enum' in override:
        values = override['enum']
        if not isinstance(values, list) or not values:
            raise ValueError('parameter enum must be nonempty')
        for value in values:
            if not jsonschema.Draft202012Validator(base).is_valid(value):
                raise ValueError('parameter override expands trusted choices')
        result['enum'] = copy.deepcopy(values)
    jsonschema.Draft202012Validator.check_schema(result)
    if 'enum' in result and any(not jsonschema.Draft202012Validator(result).is_valid(value) for value in result['enum']):
        raise ValueError('parameter enum contradicts narrowed bounds')
    if result.get('type') == 'integer' and math.ceil(result.get('minimum', 0)) > math.floor(result.get('maximum', 0)):
        raise ValueError('integer parameter range is empty')
    return result


def validate_search_space(task, space):
    from study.problem import _fields, _names
    _fields(space, ['preset', 'models', 'parameters', 'preprocessing'], ['preset', 'models'], context='search_space')
    if space['preset'] not in (task, task + '_small'):
        raise ValueError('search_space preset must match the trusted task')
    space = copy.deepcopy(space)
    space['preset'] = task + '_small'
    _names(space['models'], 'models')
    parameters = _parameters(task)
    if not set(space['models']) <= set(parameters):
        raise ValueError('model is outside trusted task preset')
    preprocess = space.setdefault('preprocessing', ['standard', 'none'])
    _names(preprocess, 'preprocessing')
    if not set(preprocess) <= {'standard', 'none'}:
        raise ValueError('unsupported preprocessing')
    overrides = space.setdefault('parameters', {})
    if not isinstance(overrides, dict) or not set(overrides) <= set(space['models']):
        raise ValueError('parameter overrides must name allowed models')
    for model, settings in overrides.items():
        if not isinstance(settings, dict) or not set(settings) <= set(parameters[model]):
            raise ValueError('unknown model parameters')
        for name, override in settings.items():
            _narrow(parameters[model][name], override)
    return space


def _default(schema, candidate):
    validator = jsonschema.Draft202012Validator(schema)
    if validator.is_valid(candidate):
        return candidate
    if 'enum' in schema:
        return schema['enum'][0]
    value = min(schema.get('maximum', math.inf), max(schema.get('minimum', -math.inf), candidate if isinstance(candidate, (int, float)) else 1))
    if schema.get('type') == 'integer':
        value = math.ceil(value)
    if not validator.is_valid(value):
        raise ValueError('parameter override has no usable bounded default')
    return value


class TabularAdapter:
    version = 1

    def __init__(self, problem):
        self.problem = problem
        self.id = problem.task
        self.parameters = _parameters(problem.task)
        space = problem.search_space
        self.parameters = {model: self.parameters[model] for model in space['models']}
        for model, settings in space['parameters'].items():
            for name, override in settings.items():
                self.parameters[model][name] = _narrow(self.parameters[model][name], override)
        self.analysis_schema = {'type': 'object', 'additionalProperties': False, 'required': ['model', 'preprocessing', 'params'], 'properties': {'model': {'enum': space['models']}, 'preprocessing': {'enum': space['preprocessing']}, 'params': {'type': 'object'}}, 'allOf': [{'if': {'properties': {'model': {'const': model}}}, 'then': {'properties': {'params': {'type': 'object', 'properties': params, 'additionalProperties': False}}}} for model, params in self.parameters.items()]}
        preferred = 'logistic' if problem.task == 'tabular_classification' else 'ridge'
        model = preferred if preferred in space['models'] else space['models'][0]
        self.reference_config = {'model': model, 'preprocessing': 'standard' if 'standard' in space['preprocessing'] else space['preprocessing'][0], 'params': {name: _default(schema, DEFAULTS[model][name]) for name, schema in self.parameters[model].items()}}
        self.validate_config(self.reference_config)

    def validate_config(self, config):
        try:
            json.dumps(config, allow_nan=False)
            jsonschema.Draft202012Validator(self.analysis_schema).validate(config)
        except (ValueError, TypeError, jsonschema.ValidationError) as exc:
            raise ValueError(f'Invalid bounded pipeline configuration: {exc}') from exc

    def build_pipeline(self, config, *, seed):
        from study.science import _validate_seed
        self.validate_config(config)
        _validate_seed(seed)
        model = config['model']
        params = {name: _default(schema, DEFAULTS[model][name]) for name, schema in self.parameters[model].items()} | config['params']
        classification = self.problem.task == 'tabular_classification'
        if model == 'logistic':
            estimator = LogisticRegression(**params, solver='lbfgs', random_state=seed)
        elif model == 'ridge':
            estimator = Ridge(**params)
        elif model == 'random_forest':
            estimator = (RandomForestClassifier if classification else RandomForestRegressor)(**params, random_state=seed, n_jobs=1)
        else:
            estimator = (HistGradientBoostingClassifier if classification else HistGradientBoostingRegressor)(**params, random_state=seed, early_stopping=True, validation_fraction=.1, n_iter_no_change=10)
        return Pipeline([('scale', StandardScaler() if config['preprocessing'] == 'standard' else 'passthrough'), ('classifier' if classification else 'regressor', estimator)])

    def metrics(self, pipeline, X, y):
        from study.problem import validate_metric_value
        definition = self.problem.to_dict()
        names = [self.problem.objective['metric'], *definition['evaluation']['additional_metrics']]
        predictions = pipeline.predict(X) if any(name not in ('roc_auc', 'roc_auc_ovr_macro') for name in names) else None
        values = {}
        for name in names:
            if name == 'roc_auc':
                classes = list(pipeline.classes_)
                positive = self.problem.dataset['positive_class']
                if len(classes) != 2 or positive not in classes:
                    raise ValueError('roc_auc needs exactly two classes including positive_class')
                score = roc_auc_score(np.asarray(y) == positive, pipeline.predict_proba(X)[:, classes.index(positive)])
            elif name == 'roc_auc_ovr_macro':
                classes = np.asarray(pipeline.classes_)
                labels = np.asarray(y)
                if len(classes) < 3 or len(set(classes.tolist())) != len(classes):
                    raise ValueError('roc_auc_ovr_macro requires at least three distinct fitted classes')
                if set(labels.tolist()) != set(classes.tolist()):
                    raise ValueError('roc_auc_ovr_macro evaluation must contain all fitted classes')
                probabilities = np.asarray(pipeline.predict_proba(X))
                if probabilities.shape != (len(labels), len(classes)):
                    raise ValueError('roc_auc_ovr_macro probability columns must align with fitted classes')
                # Explicit column pairing also supports non-sorted class order.
                score = np.mean([roc_auc_score(labels == label, probabilities[:, column]) for column, label in enumerate(classes)])
            elif name == 'accuracy': score = accuracy_score(y, predictions)
            elif name == 'macro_f1': score = f1_score(y, predictions, average='macro', zero_division=0)
            elif name == 'rmse': score = math.sqrt(mean_squared_error(y, predictions))
            elif name == 'mae': score = mean_absolute_error(y, predictions)
            else: score = r2_score(y, predictions)
            values[name] = float(score)
            validate_metric_value(name, values[name])
        return values

    def describe(self, data_dir):
        manifest = json.loads((Path(data_dir) / 'manifest.json').read_text())
        return {'dataset': self.problem.id, 'task': self.problem.task, 'brief': self.problem.brief, 'objective': self.problem.objective, 'targets': self.problem.targets, 'feature_names': manifest['feature_names'], 'counts': {name: manifest['partitions'][name]['rows'] for name in ('train', 'validation')}, 'preprocessing': 'Fit on training partition only', 'analysis_schema': copy.deepcopy(self.analysis_schema), 'adapter': {'id': self.id, 'version': self.version}, 'data_fingerprint': manifest['data_fingerprint'], 'split_seed': manifest['seed']}

    async def run_trial(self, data_dir, trial_dir, config, *, seed, timeout):
        from study.science import run_trial
        return await run_trial(data_dir, trial_dir, config, seed=seed, timeout=timeout)


def get_adapter(problem):
    if problem.task not in ('tabular_classification', 'tabular_regression'):
        raise ValueError('unsupported trusted task adapter')
    return TabularAdapter(problem)


def worker_problem(problem):
    """Send scientific choices without original source paths or held-out arrays."""
    from study.problem import ProblemSpec
    value = problem.to_dict()
    value['brief'] = 'Trusted isolated training and validation operation.'
    value['dataset'] = {'format': 'synthetic', **({'positive_class': problem.dataset['positive_class']} if 'positive_class' in problem.dataset else {})}
    if 'roc_auc_ovr_macro' in [problem.objective['metric'], *value['evaluation']['additional_metrics']]:
        value['dataset']['n_classes'] = 3
    value['evaluation']['split'] = {'train': .6, 'validation': .2, 'test': .2, 'seed': 42}
    return ProblemSpec.from_dict(value).to_dict()
