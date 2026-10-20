"""Pure, advisory experiment descriptions; never fit, reuse, or suppress trials."""
from __future__ import annotations

import hashlib
import json
import math

import sklearn

DIAGNOSTICS_VERSION = 1


def _feature_count(project):
    count = project.get('n_features')
    if type(count) is int and count > 0:
        return count
    names = project.get('feature_names')
    if isinstance(names, (list, tuple)) and names:
        return len(names)
    return None


def pipeline_effective_config(pipeline, config, *, n_features=None):
    """Describe constructor parameters, resolving RF feature-count aliases only.

    Works on either an unfitted constructor or the actual fitted worker pipeline.
    Preprocessing remains explicit even for trees: finite precision can matter.
    """
    estimator = pipeline.steps[-1][1]
    params = estimator.get_params(deep=False).copy()
    # Only real-valued knobs have interchangeable integer/float spelling.
    # In particular RF max_features=1 and =1.0 have different meanings.
    for name in ('C', 'alpha', 'learning_rate', 'l2_regularization'):
        if name in params:
            params[name] = float(params[name])
    if config['model'] == 'random_forest' and n_features is not None:
        choice = params['max_features']
        if choice == 'sqrt':
            params['max_features'] = max(1, int(math.sqrt(n_features)))
        elif choice == 'log2':
            params['max_features'] = max(1, int(math.log2(n_features)))
        elif isinstance(choice, float):
            params['max_features'] = max(1, int(choice * n_features))
    scale = pipeline.steps[0][1]
    return {'model': config['model'], 'preprocessing': config['preprocessing'],
            'preprocessing_params': scale.get_params(deep=False) if config['preprocessing'] == 'standard' else {},
            'estimator': type(estimator).__module__ + '.' + type(estimator).__qualname__, 'params': params}


def _fingerprint(effective_config, provenance):
    payload = {'effective_config': effective_config, 'provenance': provenance}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def describe_experiment(config, *, problem, project, seed):
    """Return serializable effective_config, fingerprint and safe provenance.

    Uses the same unfitted constructors as execution. Unknown feature counts
    leave sqrt/log2 symbolic, so they cannot be falsely declared equivalent.
    The explicit legacy project marker preserves the legacy constructor path
    even when a controller has resolved a compatibility ProblemSpec.
    """
    from .science import LEGACY_CONSTRUCTOR_VERSION, build_pipeline
    from .tasks import get_adapter

    project = project or {}
    generic = problem is not None and project.get('constructor') != 'legacy'
    adapter = get_adapter(problem) if generic else None
    pipeline = (adapter.build_pipeline if adapter else build_pipeline)(config, seed=seed)
    n_features = _feature_count(project)
    effective = pipeline_effective_config(pipeline, config, n_features=n_features)
    objective = problem.objective if generic else {'metric': 'roc_auc', 'direction': 'maximize'}
    provenance = {
        'diagnostics_version': DIAGNOSTICS_VERSION,
        'constructor': 'tabular_adapter' if generic else 'legacy',
        'constructor_version': adapter.version if adapter else LEGACY_CONSTRUCTOR_VERSION,
        'sklearn_version': sklearn.__version__,
        'task': problem.task if generic else 'tabular_classification',
        'metric': objective['metric'], 'direction': objective['direction'],
        'split': 'validation', 'seed': seed, 'n_features': n_features,
        'dataset': problem.id if generic else project.get('dataset'),
        'data_fingerprint': project.get('data_fingerprint'),
        'problem_hash': problem.fingerprint if generic else None,
        'split_seed': problem.to_dict()['evaluation']['split']['seed'] if generic else project.get('split_seed'),
    }
    return {'effective_config': effective, 'fingerprint': _fingerprint(effective, provenance), 'provenance': provenance}


def experiment_diagnostic(config, *, problem, project, seed, history):
    """Describe this request and identify successful equivalent prior experiments.

    Stored metadata must be internally consistent and match all provenance.
    A legacy row without metadata can be compared only with an explicit seed.
    The return value is advisory: callers still execute every valid request.
    """
    current = describe_experiment(config, problem=problem, project=project, seed=seed)
    equivalent = []
    for prior in history:
        if not isinstance(prior, dict) or prior.get('status') != 'completed':
            continue
        trial_id = prior.get('trial_id')
        if type(trial_id) is not int or trial_id in equivalent:
            continue
        try:
            if any(key in prior for key in ('fingerprint', 'provenance', 'effective_config')):
                if prior.get('provenance') != current['provenance']:
                    continue
                fingerprint = _fingerprint(prior['effective_config'], prior['provenance'])
                if fingerprint != prior.get('fingerprint'):
                    continue
            else:
                if 'seed' not in prior:
                    continue
                fingerprint = describe_experiment(prior['config'], problem=problem, project=project, seed=prior['seed'])['fingerprint']
            if fingerprint == current['fingerprint']:
                equivalent.append(trial_id)
        except (KeyError, TypeError, ValueError):
            # Incomplete historical evidence must never create a positive match.
            continue
    warning = None
    if equivalent:
        ids = ', '.join(str(trial_id) for trial_id in equivalent)
        warning = (f'This experiment has the same effective configuration, preprocessing, seed, and validation provenance as completed trial(s) {ids}; '
                   'the runner reuses that observation without fitting or consuming a trial slot.')
    return current | {'equivalent_trial_ids': equivalent, 'warning': warning}
