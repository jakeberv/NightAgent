"""Prepare a deterministic Fashion-MNIST pilot source without model calls.

Official gzip checksums: https://github.com/zalandoresearch/fashion-mnist#get-the-data
The NPZ preserves original uint8 images and all official test examples. The
problem profile subsequently flattens images and splits the selected training
pool; this module records that intended split's original source row indices.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import struct
import tempfile
import zlib

import httpx
import numpy as np
import sklearn
from sklearn.model_selection import train_test_split

SOURCE_BASE = 'https://raw.githubusercontent.com/zalandoresearch/fashion-mnist/master/data/fashion/'
SOURCE_FILES = {
    'train_images': {'filename': 'train-images-idx3-ubyte.gz', 'kind': 'images',
                     'count': 60000, 'md5': '8d4fb7e6c68d591d4c3dfef9ec88bf0d'},
    'train_labels': {'filename': 'train-labels-idx1-ubyte.gz', 'kind': 'labels',
                     'count': 60000, 'md5': '25c81989df183df01b3e8a0aad5dffbe'},
    'test_images': {'filename': 't10k-images-idx3-ubyte.gz', 'kind': 'images',
                    'count': 10000, 'md5': 'bef4ecab320f06d8554ea6380940ec79'},
    'test_labels': {'filename': 't10k-labels-idx1-ubyte.gz', 'kind': 'labels',
                    'count': 10000, 'md5': 'bb300cfdad3c16e7a12a480ee83cd310'},
}
MAX_DOWNLOAD_BYTES = 32 * 1024 * 1024


def read_idx_gzip(path, *, kind, expected_count):
    """Validate exact unsigned-byte IDX shape/length before exposing an array."""
    if kind not in ('images', 'labels') or type(expected_count) is not int or expected_count <= 0:
        raise ValueError('IDX needs an image/label kind and positive expected count')
    header_size = 16 if kind == 'images' else 8
    expected_size = header_size + expected_count * (784 if kind == 'images' else 1)
    try:
        with gzip.open(path, 'rb') as stream:
            raw = stream.read(expected_size + 1)
    except (OSError, EOFError, zlib.error) as error:
        raise ValueError(f'Invalid gzip IDX file: {path}') from error
    if len(raw) != expected_size:
        raise ValueError(f'IDX length does not match expected count and dimensions: {path}')
    magic, count = struct.unpack('>II', raw[:8])
    if magic != (2051 if kind == 'images' else 2049) or count != expected_count:
        raise ValueError(f'IDX magic or example count mismatch: {path}')
    if kind == 'images' and struct.unpack('>II', raw[8:16]) != (28, 28):
        raise ValueError(f'IDX image dimensions must be 28 by 28: {path}')
    values = np.frombuffer(raw, dtype=np.uint8, offset=header_size).copy()
    if kind == 'images':
        return values.reshape(count, 28, 28)
    if np.any(values > 9):
        raise ValueError(f'Fashion-MNIST labels must be in 0..9: {path}')
    return values


def _hash(path, algorithm='sha256'):
    digest = hashlib.new(algorithm)
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _source_file(cache, spec):
    path = cache / spec['filename']
    url = SOURCE_BASE + spec['filename']
    if not path.exists():
        cache.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=cache, prefix='.download-', delete=False) as handle:
                temporary = Path(handle.name)
                with httpx.stream('GET', url, timeout=60, trust_env=False, follow_redirects=False) as response:
                    response.raise_for_status()
                    size = 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_DOWNLOAD_BYTES:
                            raise ValueError('Fashion-MNIST download exceeds size limit')
                        handle.write(chunk)
            if _hash(temporary, 'md5') != spec['md5']:
                raise ValueError(f'Published MD5 checksum mismatch: {spec["filename"]}')
            # Exclusive install never replaces another process's cached input.
            try:
                os.link(temporary, path)
            except FileExistsError:
                pass
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    if path.stat().st_size > MAX_DOWNLOAD_BYTES or _hash(path, 'md5') != spec['md5']:
        raise ValueError(f'Published MD5 checksum mismatch: {path}; retain or remove this invalid cache explicitly')
    return path, {'url': url, 'filename': spec['filename'], 'md5': spec['md5'],
                  'sha256': _hash(path), 'bytes': path.stat().st_size, 'examples': spec['count']}


def _validate_request(train_size, validation_size, seed, population):
    if any(type(value) is not int or value < 10 for value in (train_size, validation_size)):
        raise ValueError('train_size and validation_size must be integers of at least 10')
    if train_size + validation_size > population:
        raise ValueError('Requested training/validation subset exceeds official training count')
    if type(seed) is not int or not 0 <= seed < 2**32:
        raise ValueError('seed must be an integer from 0 through 2**32-1')


def select_source_indices(labels, *, train_size, validation_size, seed):
    """Select using training labels alone; return original official-train indices."""
    labels = np.asarray(labels)
    if labels.ndim != 1 or not np.issubdtype(labels.dtype, np.integer) or set(np.unique(labels)) != set(range(10)):
        raise ValueError('Training labels must be one-dimensional integers containing classes 0..9')
    _validate_request(train_size, validation_size, seed, len(labels))
    total = train_size + validation_size
    indices = np.arange(len(labels))
    selected = (indices if total == len(indices) else train_test_split(
        indices, train_size=total, random_state=seed, stratify=labels)[0])
    # Match study.science's official-test split, including order and float fraction.
    train, validation = train_test_split(np.arange(total), test_size=validation_size / total,
                                        random_state=seed, stratify=labels[selected])
    if len(train) != train_size or len(validation) != validation_size:
        raise ValueError('Requested sizes cannot be represented by the profile split fraction exactly')
    return {'selected': selected, 'train': selected[train], 'validation': selected[validation]}


def prepare_fashion_data(output, *, train_size=12000, validation_size=3000, seed=42, cache=None):
    """Create immutable NPZ and sidecar manifest, or verify an identical rerun."""
    output = Path(output)
    if output.suffix != '.npz':
        raise ValueError('output must have an .npz extension')
    _validate_request(train_size, validation_size, seed, SOURCE_FILES['train_labels']['count'])
    manifest_path = output.with_suffix('.manifest.json')
    request = {'train_size': train_size, 'validation_size': validation_size, 'seed': seed,
               'sources': {key: SOURCE_BASE + spec['filename'] + '#' + spec['md5']
                           for key, spec in SOURCE_FILES.items()}}
    if output.exists() or manifest_path.exists():
        if not output.is_file() or not manifest_path.is_file():
            raise ValueError('Immutable output is incomplete; choose a new output path')
        try:
            existing = json.loads(manifest_path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise ValueError('Immutable output manifest is invalid') from error
        if not isinstance(existing, dict):
            raise ValueError('Immutable output manifest must be an object')
        if existing.get('schema_version') != 1 or existing.get('request') != request:
            raise ValueError('Immutable output has different source or selection parameters; choose a new output path')
        if existing.get('output_sha256') != _hash(output):
            raise ValueError('Output checksum changed; immutable source integrity check failed')
        return existing
    cache = Path(cache) if cache is not None else output.parent / 'fashion-mnist-cache'
    arrays, sources = {}, {}
    for key, spec in SOURCE_FILES.items():
        path, sources[key] = _source_file(cache, spec)
        arrays[key] = read_idx_gzip(path, kind=spec['kind'], expected_count=spec['count'])
    if len(arrays['train_images']) != len(arrays['train_labels']) or len(arrays['test_images']) != len(arrays['test_labels']):
        raise ValueError('Fashion-MNIST image/label counts do not match')
    if set(np.unique(arrays['test_labels'])) != set(range(10)):
        raise ValueError('Official test labels must contain all classes 0..9')
    indices = select_source_indices(arrays['train_labels'], train_size=train_size,
                                    validation_size=validation_size, seed=seed)
    selected = indices['selected']
    manifest = {
        'schema_version': 1, 'dataset': 'Fashion-MNIST', 'request': request,
        'created_at': datetime.now(timezone.utc).isoformat(), 'sources': sources,
        'selection': {'selected_source_indices': selected.tolist(),
                      'train_source_indices': indices['train'].tolist(),
                      'validation_source_indices': indices['validation'].tolist(),
                      'official_test_indices': list(range(len(arrays['test_labels'])))},
        'selection_protocol': 'sklearn train_test_split of official training indices; stratified subset, then stratified train/validation; same seed at both stages',
        'profile_split': {'train': train_size / len(selected), 'validation': validation_size / len(selected),
                          'test': 'official', 'seed': seed},
        'class_counts': {name: np.bincount(arrays['train_labels'][ids], minlength=10).tolist()
                         for name, ids in indices.items()},
        'versions': {'numpy': np.__version__, 'scikit_learn': sklearn.__version__},
        'source_index_namespaces': {'selected_source_indices': 'official training IDX, zero-based',
                                    'train_source_indices': 'official training IDX, zero-based',
                                    'validation_source_indices': 'official training IDX, zero-based',
                                    'official_test_indices': 'official test IDX, zero-based; separate from training'},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = manifest_temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.fashion-', delete=False) as handle:
            temporary = Path(handle.name)
            np.savez_compressed(handle, x_train=arrays['train_images'][selected],
                                y_train=arrays['train_labels'][selected],
                                x_test=arrays['test_images'], y_test=arrays['test_labels'])
        manifest['output_sha256'] = _hash(temporary)
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix='.fashion-manifest-', mode='w',
                                         encoding='utf-8', delete=False) as handle:
            manifest_temporary = Path(handle.name)
            json.dump(manifest, handle, indent=2)
            handle.write('\n')
        os.link(temporary, output)
        os.link(manifest_temporary, manifest_path)
    finally:
        for path in (temporary, manifest_temporary):
            if path is not None:
                path.unlink(missing_ok=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--train-size', type=int, default=12000)
    parser.add_argument('--validation-size', type=int, default=3000)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--cache', type=Path, help='Verified official gzip cache (default: beside output)')
    args = parser.parse_args(argv)
    try:
        manifest = prepare_fashion_data(args.output, train_size=args.train_size,
                                       validation_size=args.validation_size, seed=args.seed, cache=args.cache)
    except (OSError, ValueError, httpx.HTTPError) as error:
        parser.exit(1, f'Fashion-MNIST preparation failed: {error}\n')
    print(json.dumps({'output': str(args.output), 'manifest': str(args.output.with_suffix('.manifest.json')),
                      'output_sha256': manifest['output_sha256'], 'profile_split': manifest['profile_split']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
