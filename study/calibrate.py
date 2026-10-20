"""Sequential validation-only model calibration, without API calls or credentials.

Example: python -m study.calibrate --data study-data/fashion-pilot
--output study-runs/fashion-calibration --configs study/fashion-calibration-configs.json
--device mps --max-cores 4 --trial-timeout 120
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
from pathlib import Path
import time

from .events import atomic_json, utc_now
from .problem import problem_from_data, prepared_data_fingerprint
from .resources import BalancedTrials, CorePool, validate_cores
from .science import _hash_file, _validate_seed, run_trial
from .tasks import get_adapter


def _prepared_problem(data):
    """Validate frozen identity and fitting partitions without opening test data."""
    problem = problem_from_data(data)
    if problem is None:
        raise ValueError('Calibration requires a prepared problem profile')
    manifest = json.loads((data / 'manifest.json').read_text(encoding='utf-8'))
    split = problem.to_dict()['evaluation']['split']
    if (manifest.get('dataset') != problem.id or manifest.get('seed') != split['seed']
            or manifest.get('split_protocol') != split):
        raise ValueError('Prepared dataset identity or split mismatch')
    if 'adapter' in manifest:
        raise ValueError('Refresh prepared metadata with study prepare before calibration')
    if manifest.get('data_fingerprint') != prepared_data_fingerprint(manifest):
        raise ValueError('Prepared data fingerprint mismatch')
    for name in ('train', 'validation'):
        if _hash_file(data / f'{name}.npz') != manifest['partitions'][name]['sha256']:
            raise ValueError(f'{name} partition fingerprint mismatch')
    return problem, manifest


async def calibrate(data, output, configs, *, device='auto', max_cores=4, trial_timeout=120):
    """Validate all inputs, then save every sequential trial to a new directory."""
    data, output = Path(data).resolve(), Path(output).resolve()
    if output.exists():
        raise ValueError('Calibration output is immutable and already exists; choose a new output directory')
    validate_cores(max_cores)
    if type(trial_timeout) not in (int, float) or not math.isfinite(trial_timeout) or trial_timeout <= 0:
        raise ValueError('trial_timeout must be positive and finite')
    if device not in ('auto', 'cpu', 'mps'):
        raise ValueError('device must be auto, cpu, or mps')
    if not isinstance(configs, list) or not configs:
        raise ValueError('configs must be a nonempty JSON list of bounded configuration objects')
    problem, manifest = _prepared_problem(data)
    adapter = get_adapter(problem)
    for index, config in enumerate(configs, 1):
        try:
            adapter.validate_config(config)
        except ValueError as error:
            raise ValueError(f'Invalid calibration config {index}: {error}') from error
    # Snapshot the entire plan before asynchronous work can begin.
    configs = json.loads(json.dumps(configs, allow_nan=False))
    seed = manifest['seed']
    _validate_seed(seed)
    actual_device = 'cpu'
    if any(config['model'].startswith('torch_') for config in configs):
        from .torch_models import resolve_device
        actual_device = resolve_device(device)
    pool = CorePool(max_cores)
    runner = BalancedTrials(pool, runner=run_trial, device=actual_device)
    result = {
        'schema_version': 1, 'status': 'running', 'started_at': utc_now(),
        'data': str(data), 'problem_hash': problem.fingerprint,
        'data_fingerprint': manifest['data_fingerprint'], 'objective': problem.objective,
        'api_calls': 0, 'evaluation_partition': 'validation', 'seed': seed,
        'requested_device': device, 'device': actual_device,
        'requested_max_cores': max_cores, 'max_cores': pool.limit,
        'trial_timeout_seconds': trial_timeout, 'configs': configs,
        'configs_sha256': hashlib.sha256(json.dumps(configs, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
        'results': [], 'active_trial': None,
    }
    try:
        output.mkdir(parents=True, exist_ok=False)
    except FileExistsError as error:
        raise ValueError('Calibration output already exists; choose a new output directory') from error
    path = output / 'calibration.json'
    atomic_json(path, result)
    started = time.monotonic()
    for index, config in enumerate(configs, 1):
        trial_dir = output / 'trials' / f'{index:03d}'
        result['active_trial'] = {'index': index, 'config': config, 'directory': str(trial_dir)}
        atomic_json(path, result)
        trial_started = time.monotonic()
        try:
            observed = await runner(data, trial_dir, config, seed=seed, timeout=trial_timeout)
        except asyncio.CancelledError:
            result['results'].append({'index': index, 'config': config, 'status': 'cancelled',
                                      'total_wall_seconds': time.monotonic() - trial_started})
            result.update(status='interrupted', active_trial=None, finished_at=utc_now(),
                          total_wall_seconds=time.monotonic() - started)
            atomic_json(path, result)
            raise
        except Exception as error:
            observed = {'status': 'failed', 'error': f'{type(error).__name__}: {error}'}
        result['results'].append({**observed, 'index': index, 'config': config,
                                  'execution_device': actual_device if config['model'].startswith('torch_') else 'cpu',
                                  'total_wall_seconds': time.monotonic() - trial_started})
        result['active_trial'] = None
        result['total_wall_seconds'] = time.monotonic() - started
        atomic_json(path, result)
    result.update(status='completed' if all(row.get('status') == 'completed' for row in result['results']) else 'failed',
                  finished_at=utc_now(), total_wall_seconds=time.monotonic() - started)
    atomic_json(path, result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--configs', type=Path, required=True,
                        help='JSON list of bounded pipeline configuration objects')
    parser.add_argument('--device', choices=('auto', 'cpu', 'mps'), default='auto')
    parser.add_argument('--max-cores', type=int, default=4)
    parser.add_argument('--trial-timeout', type=float, default=120)
    args = parser.parse_args(argv)
    try:
        configs = json.loads(args.configs.read_text(encoding='utf-8'))
        result = asyncio.run(calibrate(args.data, args.output, configs, device=args.device,
                                      max_cores=args.max_cores, trial_timeout=args.trial_timeout))
    except KeyboardInterrupt:
        print(f'Calibration interrupted; recorded progress: {args.output / "calibration.json"}')
        return 130
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        parser.exit(1, f'Calibration failed: {error}\n')
    print(json.dumps({'status': result['status'], 'calibration': str(args.output / 'calibration.json'),
                      'trials': len(result['results']), 'api_calls': 0}))
    return 0 if result['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
