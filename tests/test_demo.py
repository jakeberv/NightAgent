"""Replay exports must preserve evidence and keep fixtures out of strategy claims."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.fake import FakeModel
from study.report_data import build_report_data
from study.science import prepare_dataset
from study.suite import run_suite


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value) + '\n')


@pytest.fixture(scope='module')
def recording(tmp_path_factory):
    """Tiny scripted records exercise replay plumbing, never model performance."""
    root = tmp_path_factory.mktemp('demo-recording')
    data = root / 'data'
    prepare_dataset(data, synthetic=True)

    class PairModel(FakeModel):
        async def complete(self, messages, tools, *, timeout):
            response = await super().complete(messages, tools, timeout=timeout)
            context = json.loads(messages[1]['content'])
            if messages[0]['content'].startswith('ROLE: reflection'):
                contract = json.loads(response['message']['content'])
                if len(context['recent_trials']) >= 2 and 'lessons' in context:
                    previous = context['recent_trials'][-2]
                    contract['lesson_updates'][0]['evidence'].append(
                        {'trial_id': previous['trial_id'], 'metric': 'roc_auc'})
                    response['message']['content'] = json.dumps(contract)
            return response

    async def fit(data_dir, trial_dir, config, *, seed, timeout):
        trial_dir.mkdir(parents=True)
        artifact = trial_dir / 'model.joblib'
        artifact.write_bytes(f'fixture {seed} {config}'.encode())
        return {'status': 'completed', 'metrics': {'roc_auc': .94}, 'score': .94,
                'artifact': str(artifact), 'artifact_hash': hashlib.sha256(artifact.read_bytes()).hexdigest()}

    async def runner(config, data_dir, run_dir, model, **kwargs):
        kwargs.pop('trial_runner', None)
        return await run_one(config, data_dir, run_dir, model, trial_runner=fit, **kwargs)

    config = StudyConfig(comparison='apprentice_interactions', model='offline-script', provider='offline',
                         device='cpu', trial_cap=7, allowance_seconds=60, max_cores=4)
    suite = root / 'suite'
    asyncio.run(run_suite(config, data, suite, repeats=1,
        deadline=datetime.now(timezone.utc) + timedelta(hours=1), reserve_seconds=600,
        model_factory=lambda _: PairModel(options=[{'model': 'logistic', 'preprocessing': 'standard',
                                                    'params': {'C': i}} for i in range(1, 8)]),
        runner=runner, validation_only=True))
    write(suite / 'completion.json', {'postrun': {'evaluate': 'skipped_validation_only', 'report': 'completed'}})
    report = build_report_data(suite)
    write(suite / 'paired-comparisons.json', report['paired_comparisons'])
    write(suite / 'strategy-efficiency.json', {name: value['targets'] for name, value in report['conditions'].items()})
    (suite / 'report.html').write_text('<html>offline fixture</html>')
    return suite


@pytest.fixture
def suite(recording, tmp_path):
    target = tmp_path / 'suite'
    shutil.copytree(recording, target)
    for path in target.rglob('*'):
        if path.suffix in ('.json', '.jsonl'):
            path.write_text(path.read_text().replace(str(recording), str(target)))
    return target


def test_cli_exports_portable_replay_and_explicitly_labels_offline_evidence(suite, tmp_path):
    output = tmp_path / 'replay'
    before = {p.relative_to(suite): p.read_bytes() for p in suite.rglob('*') if p.is_file()}
    process = subprocess.run([sys.executable, '-m', 'study.demo', '--suite', str(suite),
                              '--output', str(output)], text=True, capture_output=True)
    assert process.returncode == 0, process.stdout + process.stderr
    demo = read(output / 'demo.json')
    assert demo['evidence_kind'] == 'offline_fixture'
    assert demo['strategy_evidence'] is False
    assert len(demo['arms']) == 5
    assert demo['selected_arm'] == 'periodic_reflection'
    assert demo['selected_run'] == 'r00-periodic_reflection'
    assert demo['chain']['baseline']['trial_id'] == 1
    assert demo['chain']['result']['trial_id'] == 2
    assert demo['chain']['changes'] == [{'field': 'params.C', 'before': 1, 'after': 2}]
    assert demo['chain']['result']['score'] == .94
    assert demo['chain']['delivery']['role'] == 'researcher'
    assert demo['chain']['delivery']['before_trial_id'] == 3
    assert {citation['trial_id'] for citation in demo['chain']['lesson']['evidence']} == {1, 2}
    assert str(suite) not in (output / 'demo.json').read_text()
    assert 'not evidence of a strategy advantage' in (output / 'demo.md').read_text()
    assert {p.relative_to(suite): p.read_bytes() for p in suite.rglob('*') if p.is_file()} == before


@pytest.mark.parametrize('mutation', ['missing_journal', 'corrupt_journal', 'artifact', 'context'])
def test_replay_rejects_missing_or_tampered_evidence_before_creating_output(suite, tmp_path, mutation):
    from study.demo import generate_demo
    run = suite / 'runs/r00-periodic_reflection'
    journal = run / 'events.jsonl'
    if mutation == 'missing_journal':
        journal.unlink()
    elif mutation == 'corrupt_journal':
        with journal.open('a') as handle:
            handle.write('{"type":')
    elif mutation == 'artifact':
        (run / 'trials/0001/model.joblib').write_bytes(b'tampered')
    else:
        events = [json.loads(line) for line in journal.read_text().splitlines()]
        for event in events:
            if event['type'] == 'model_call_started' and event['role'] == 'researcher':
                context = json.loads(event['messages'][1]['content'])
                context['lessons'] = []
                event['messages'][1]['content'] = json.dumps(context)
        journal.write_text(''.join(json.dumps(e) + '\n' for e in events))
    output = tmp_path / 'rejected'
    with pytest.raises(ValueError, match='audit'):
        generate_demo(suite, output)
    assert not output.exists()


def test_generation_uses_no_network_and_cannot_write_inside_the_source_suite(suite, tmp_path, monkeypatch):
    from study.demo import generate_demo
    def forbidden(*args, **kwargs):
        raise AssertionError('Replay attempted network access')
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    import study.science as science
    import study.provider as provider
    monkeypatch.setattr(provider.OpenRouter, '__init__', forbidden)
    monkeypatch.setattr(science, 'run_trial', forbidden)
    monkeypatch.setattr(science, 'evaluate_selected', forbidden)
    generate_demo(suite, tmp_path / 'offline')
    with pytest.raises(ValueError, match='outside'):
        generate_demo(suite, suite / 'replay')


@pytest.fixture
def reference(suite, tmp_path):
    manifest = read(suite / 'suite.json')
    reference = tmp_path / 'reference'
    reference.mkdir()
    artifact = reference / 'model.joblib'
    artifact.write_bytes(b'fixed reference artifact')
    result = {'status': 'completed', 'score': .8, 'metrics': {'roc_auc': .8},
              'config': {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': 1.0, 'max_iter': 300}},
              'seed': 42, 'artifact': str(artifact),
              'artifact_hash': hashlib.sha256(artifact.read_bytes()).hexdigest(),
              'provenance': {key: manifest[key] for key in ('problem_hash', 'data_fingerprint')} |
                            {'metric': 'roc_auc', 'direction': 'maximize', 'split': 'validation'}}
    write(reference / 'result.json', result)
    return reference / 'result.json'


def test_reference_requires_matching_identity_and_verified_artifact(suite, reference):
    from study.demo import build_demo
    manifest = read(suite / 'suite.json')
    result = read(reference)
    assert build_demo(suite, reference=reference)['reference']['score'] == .8
    result['provenance']['data_fingerprint'] = 'wrong'
    write(reference, result)
    with pytest.raises(ValueError, match='identity'):
        build_demo(suite, reference=reference)
    result['provenance']['data_fingerprint'] = manifest['data_fingerprint']
    write(reference, result)
    Path(result['artifact']).write_bytes(b'tampered')
    with pytest.raises(ValueError, match='hash'):
        build_demo(suite, reference=reference)


@pytest.mark.parametrize('mutation, message', [
    ('inside_suite', 'separate'), ('adaptive_config', 'fixed configuration'),
    ('heldout', 'validation'), ('missing_split', 'validation'),
    ('missing_metric', 'objective'), ('wrong_direction', 'objective')])
def test_reference_cannot_relabel_adaptive_or_nonvalidation_evidence(suite, reference, mutation, message):
    from study.demo import build_demo
    result = read(reference)
    if mutation == 'inside_suite':
        copied = suite / 'separate-looking-reference'
        shutil.copytree(reference.parent, copied)
        result['artifact'] = str(copied / 'model.joblib')
        reference = copied / 'result.json'
    elif mutation == 'adaptive_config':
        result['config'] = {'model': 'random_forest', 'preprocessing': 'standard',
                            'params': {'n_estimators': 100, 'max_depth': 20}}
    elif mutation == 'heldout':
        result['provenance']['split'] = 'test'
    elif mutation == 'missing_split':
        del result['provenance']['split']
    elif mutation == 'missing_metric':
        del result['provenance']['metric']
    elif mutation == 'wrong_direction':
        result['provenance']['direction'] = 'minimize'
    write(reference, result)
    with pytest.raises(ValueError, match=message):
        build_demo(suite, reference=reference)
