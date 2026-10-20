"""Fashion source preparation freezes provenance without using held-out examples."""
import gzip
import hashlib
import json
from pathlib import Path
import struct

import numpy as np
import pytest


def idx(values, kind):
    values = np.asarray(values, dtype=np.uint8)
    dims = values.shape
    return struct.pack('>II', 2051 if kind == 'images' else 2049, dims[0]) + (
        struct.pack('>II', *dims[1:]) if kind == 'images' else b'') + values.tobytes()


def test_read_idx_retains_original_pixels_and_labels(tmp_path):
    from study.fashion_data import read_idx_gzip
    for kind, values in [('images', np.arange(1568, dtype=np.uint16).astype(np.uint8).reshape(2, 28, 28)),
                         ('labels', np.array([0, 9], dtype=np.uint8))]:
        path = tmp_path / (kind + '.gz')
        path.write_bytes(gzip.compress(idx(values, kind)))
        actual = read_idx_gzip(path, kind=kind, expected_count=2)
        assert actual.dtype == np.uint8
        np.testing.assert_array_equal(actual, values)


@pytest.mark.parametrize('payload,kind,count', [
    (b'bad', 'images', 2),
    (struct.pack('>IIII', 2049, 2, 28, 28) + bytes(1568), 'images', 2),
    (struct.pack('>IIII', 2051, 2, 28, 27) + bytes(1512), 'images', 2),
    (struct.pack('>IIII', 2051, 2, 28, 28) + bytes(1567), 'images', 2),
    (struct.pack('>IIII', 2051, 2, 28, 28) + bytes(1569), 'images', 2),
    (struct.pack('>II', 2049, 3) + bytes([0, 1, 2]), 'labels', 2),
    (struct.pack('>II', 2049, 2) + bytes([0, 10]), 'labels', 2),
], ids=['short-header', 'wrong-magic', 'wrong-dimensions', 'short-body', 'long-body', 'wrong-count', 'bad-label'])
def test_rejects_malformed_idx_dimensions_length_counts_and_labels(tmp_path, payload, kind, count):
    from study.fashion_data import read_idx_gzip
    path = tmp_path / 'bad.gz'
    path.write_bytes(gzip.compress(payload))
    with pytest.raises(ValueError, match='(?i)(IDX|label|count|dimension|length)'):
        read_idx_gzip(path, kind=kind, expected_count=count)


def test_rejects_truncated_gzip(tmp_path):
    from study.fashion_data import read_idx_gzip
    path = tmp_path / 'truncated.gz'
    path.write_bytes(gzip.compress(idx([0, 1], 'labels'))[:-4])
    with pytest.raises(ValueError, match='(?i)(gzip|IDX)'):
        read_idx_gzip(path, kind='labels', expected_count=2)


def test_selection_is_stratified_deterministic_and_has_disjoint_original_ids():
    from study.fashion_data import select_source_indices
    labels = np.repeat(np.arange(10, dtype=np.uint8), 100)
    first = select_source_indices(labels, train_size=120, validation_size=30, seed=42)
    second = select_source_indices(labels, train_size=120, validation_size=30, seed=42)
    for key in first:
        np.testing.assert_array_equal(first[key], second[key])
    train, validation, selected = first['train'], first['validation'], first['selected']
    assert len(set(train) & set(validation)) == 0
    assert len(set(selected)) == 150
    assert set(train) | set(validation) == set(selected)
    assert np.bincount(labels[train]).tolist() == [12] * 10
    assert np.bincount(labels[validation]).tolist() == [3] * 10
    assert not np.array_equal(selected, select_source_indices(labels, train_size=120, validation_size=30, seed=43)['selected'])


@pytest.mark.parametrize('train_size,validation_size,seed', [(0, 30, 42), (120, 0, 42), (999, 30, 42),
                                                            (120, 30, -1), (True, 30, 42)])
def test_selection_rejects_invalid_counts_and_seed(train_size, validation_size, seed):
    from study.fashion_data import select_source_indices
    with pytest.raises(ValueError):
        select_source_indices(np.tile(np.arange(10), 100), train_size=train_size,
                              validation_size=validation_size, seed=seed)


def source_fixture(tmp_path, monkeypatch, *, test_pixel=201):
    """Small complete source catalog exercises real parsing/cache/output paths."""
    from study import fashion_data
    cache = tmp_path / 'cache'
    cache.mkdir(exist_ok=True)
    arrays = {
        'train_images': np.arange(100 * 784, dtype=np.uint32).astype(np.uint8).reshape(100, 28, 28),
        'train_labels': np.repeat(np.arange(10, dtype=np.uint8), 10),
        'test_images': np.full((20, 28, 28), test_pixel, dtype=np.uint8),
        'test_labels': np.tile(np.arange(10, dtype=np.uint8), 2),
    }
    catalog = {}
    for key, array in arrays.items():
        kind = 'images' if key.endswith('images') else 'labels'
        filename = key + '.gz'
        payload = gzip.compress(idx(array, kind), mtime=0)
        (cache / filename).write_bytes(payload)
        catalog[key] = {'filename': filename, 'kind': kind, 'count': len(array),
                        'md5': hashlib.md5(payload).hexdigest()}
    monkeypatch.setattr(fashion_data, 'SOURCE_FILES', catalog)
    return cache, arrays


def test_prepare_saves_exact_source_ids_official_test_and_immutable_rerun(tmp_path, monkeypatch):
    from study.fashion_data import prepare_fashion_data
    cache, source = source_fixture(tmp_path, monkeypatch)
    output = tmp_path / 'pilot.npz'
    manifest = prepare_fashion_data(output, train_size=40, validation_size=10, seed=42, cache=cache)
    saved = json.loads(output.with_suffix('.manifest.json').read_text())
    assert saved == manifest
    assert saved['selection']['official_test_indices'] == list(range(20))
    assert saved['output_sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert all(len(item['sha256']) == 64 for item in saved['sources'].values())
    ids = saved['selection']['selected_source_indices']
    with np.load(output, allow_pickle=False) as data:
        assert set(data.files) == {'x_train', 'y_train', 'x_test', 'y_test'}
        np.testing.assert_array_equal(data['x_train'], source['train_images'][ids])
        np.testing.assert_array_equal(data['y_train'], source['train_labels'][ids])
        np.testing.assert_array_equal(data['x_test'], source['test_images'])
        np.testing.assert_array_equal(data['y_test'], source['test_labels'])
    before = output.read_bytes()
    assert prepare_fashion_data(output, train_size=40, validation_size=10, seed=42, cache=cache) == manifest
    with pytest.raises(ValueError, match='(?i)(immutable|different|changed)'):
        prepare_fashion_data(output, train_size=40, validation_size=10, seed=43, cache=cache)
    assert output.read_bytes() == before
    output.write_bytes(b'corrupted')
    with pytest.raises(ValueError, match='(?i)(checksum|changed|integrity)'):
        prepare_fashion_data(output, train_size=40, validation_size=10, seed=42, cache=cache)


def test_external_test_content_cannot_change_training_selection(tmp_path, monkeypatch):
    from study.fashion_data import prepare_fashion_data
    cache, _ = source_fixture(tmp_path, monkeypatch, test_pixel=201)
    a = prepare_fashion_data(tmp_path / 'a.npz', train_size=40, validation_size=10, seed=42, cache=cache)
    cache, _ = source_fixture(tmp_path, monkeypatch, test_pixel=17)
    b = prepare_fashion_data(tmp_path / 'b.npz', train_size=40, validation_size=10, seed=42, cache=cache)
    assert a['selection'] == b['selection']
    assert a['sources']['test_images']['sha256'] != b['sources']['test_images']['sha256']


def test_cached_downloads_must_match_published_md5(tmp_path, monkeypatch):
    from study.fashion_data import prepare_fashion_data
    cache, _ = source_fixture(tmp_path, monkeypatch)
    (cache / 'train_images.gz').write_bytes(b'bad')
    with pytest.raises(ValueError, match='(?i)(checksum|MD5)'):
        prepare_fashion_data(tmp_path / 'pilot.npz', train_size=40, validation_size=10, seed=42, cache=cache)
    assert not (tmp_path / 'pilot.npz').exists()


def test_prepare_manifest_split_matches_actual_profile_stratifier(tmp_path, monkeypatch):
    from sklearn.model_selection import train_test_split
    from study.fashion_data import prepare_fashion_data
    cache, _ = source_fixture(tmp_path, monkeypatch)
    path = tmp_path / 'pilot.npz'
    manifest = prepare_fashion_data(path, train_size=40, validation_size=10, seed=42, cache=cache)
    with np.load(path, allow_pickle=False) as data:
        train, validation = train_test_split(np.arange(50), test_size=.2, random_state=42, stratify=data['y_train'])
    selected = np.array(manifest['selection']['selected_source_indices'])
    assert selected[train].tolist() == manifest['selection']['train_source_indices']
    assert selected[validation].tolist() == manifest['selection']['validation_source_indices']


def test_download_checksums_before_cache_install_and_records_actual_sha(tmp_path, monkeypatch):
    from contextlib import contextmanager
    import httpx
    from study import fashion_data
    payload = gzip.compress(idx([0, 9], 'labels'), mtime=0)
    spec = {'filename': 'labels.gz', 'kind': 'labels', 'count': 2,
            'md5': hashlib.md5(payload).hexdigest()}
    def response(request):
        assert request.url.scheme == 'https'
        assert request.url.host == 'raw.githubusercontent.com'
        assert 'authorization' not in request.headers
        return httpx.Response(200, content=payload)
    @contextmanager
    def stream(method, url, **kwargs):
        with httpx.Client(transport=httpx.MockTransport(response)) as client:
            with client.stream(method, url) as result:
                yield result
    monkeypatch.setattr(fashion_data.httpx, 'stream', stream)
    path, provenance = fashion_data._source_file(tmp_path / 'cache', spec)
    assert path.read_bytes() == payload
    assert provenance['sha256'] == hashlib.sha256(payload).hexdigest()
    with pytest.raises(ValueError, match='MD5'):
        fashion_data._source_file(tmp_path / 'bad-cache', dict(spec, md5='0' * 32))
    assert not (tmp_path / 'bad-cache' / 'labels.gz').exists()
    assert list((tmp_path / 'bad-cache').iterdir()) == []


def test_cli_creates_frozen_npz_and_rejects_changed_parameters(tmp_path, monkeypatch, capsys):
    from study.fashion_data import main
    cache, _ = source_fixture(tmp_path, monkeypatch)
    output = tmp_path / 'cli.npz'
    args = ['--output', str(output), '--train-size', '40', '--validation-size', '10',
            '--seed', '42', '--cache', str(cache)]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result['output'] == str(output)
    assert output.is_file() and Path(result['manifest']).is_file()
    with pytest.raises(SystemExit) as error:
        main([*args, '--seed', '43'])
    assert error.value.code == 1


def test_corrupt_gzip_deflate_reports_validation_error(tmp_path):
    from study.fashion_data import read_idx_gzip
    path = tmp_path / 'corrupt.gz'
    path.write_bytes(b'\x1f\x8b\x08\x00' + bytes(6) + b'\x07' + bytes(8))
    with pytest.raises(ValueError, match='(?i)(gzip|IDX)'):
        read_idx_gzip(path, kind='labels', expected_count=2)


def test_fashion_profile_bounds_models_and_preserves_official_test_protocol():
    from study.problem import load_problem
    from study.tasks import get_adapter
    problem = load_problem(Path(__file__).resolve().parents[1] / 'study/problems/fashion-mnist.yaml')
    assert problem.objective == {'metric': 'accuracy', 'direction': 'maximize'}
    split = problem.to_dict()['evaluation']['split']
    assert split == {'method': 'predefined_test', 'train': .8, 'validation': .2, 'test': 'official', 'seed': 42}
    adapter = get_adapter(problem)
    adapter.validate_config({'model': 'torch_cnn', 'preprocessing': 'none',
                             'params': {'epochs': 5, 'channels': 16, 'batch_size': 512}})
    for config in [
        {'model': 'torch_cnn', 'preprocessing': 'none', 'params': {'epochs': 6}},
        {'model': 'torch_mlp', 'preprocessing': 'none', 'params': {'hidden_width': 256}},
        {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_depth': 21}},
        {'model': 'random_forest', 'preprocessing': 'none', 'params': {'max_features': 'all'}},
        {'model': 'logistic', 'preprocessing': 'standard', 'params': {'max_iter': 301}},
    ]:
        with pytest.raises(ValueError):
            adapter.validate_config(config)


def test_rerun_rejects_nonobject_manifest_without_touching_output(tmp_path, monkeypatch):
    from study.fashion_data import prepare_fashion_data
    cache, _ = source_fixture(tmp_path, monkeypatch)
    output = tmp_path / 'pilot.npz'
    prepare_fashion_data(output, train_size=40, validation_size=10, seed=42, cache=cache)
    before = output.read_bytes()
    output.with_suffix('.manifest.json').write_text('[]')
    with pytest.raises(ValueError, match='(?i)(manifest|immutable)'):
        prepare_fashion_data(output, train_size=40, validation_size=10, seed=42, cache=cache)
    assert output.read_bytes() == before
