"""Published reports preserve their input hashes and label agent claims honestly."""
import hashlib
import json

import pytest

from study.report import build_report_data, generate_report
from test_report import trial, write_run


@pytest.mark.parametrize('destination', [None, 'rendered', 'source'])
def test_complete_report_commands_keep_input_hashes_valid_on_repeat(tmp_path, monkeypatch, destination):
    from study.__main__ import main

    source = tmp_path / 'source'
    write_run(source, 'observed', trials=[trial('1', 3, .9)])
    postrun = source / 'postrun.json'
    postrun.write_text(json.dumps({'evaluation_seconds': 2, 'model_cost': 0,
                                  'reporting_seconds': 999}) + '\n')
    frozen = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    output = source if destination is None else tmp_path / destination
    command = ['study', 'report', '--output', str(source)]
    if destination is not None:
        command += ['--report-dir', str(output)]

    for _ in range(2):
        monkeypatch.setattr('sys.argv', command)
        main()
        provenance = json.loads((output / 'report-provenance.json').read_text())
        assert provenance['source'] == str(source.resolve())
        assert provenance['sha256']['postrun.json'] == hashlib.sha256(postrun.read_bytes()).hexdigest()
        for name, expected in provenance['sha256'].items():
            assert hashlib.sha256((source / name).read_bytes()).hexdigest() == expected
        assert all((source / name).read_bytes() == value for name, value in frozen.items())
        accounting = json.loads((output / 'report-accounting.json').read_text())
        assert accounting['reporting_seconds'] > 0
        assert accounting['api_calls'] == 0


def test_advice_uptake_labels_do_not_present_self_reports_as_verified_compliance(tmp_path):
    events = [{'type': 'review', 'after_trial': 1,
               'contract': {'recommendation': {'model': 'logistic', 'preprocessing': 'standard',
                                                'params': {'C': 1}}}},
              {'type': 'decision_contract', 'valid': True, 'executed': True, 'trial_id': 2,
               'contract': {'baseline_trial_id': 1, 'supervisor_response': 'followed',
                            'response_reason': 'I am following the supervisor recommendation.'}}]
    chosen = trial('2', 4, .91)
    chosen['config'] = {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': 2}}
    write_run(tmp_path, 'self-report', events=events, trials=[trial('1', 2, .9), chosen])

    report = generate_report(tmp_path).read_text()
    assert 'Researcher-reported' in report
    assert 'Reported followed fraction' in report
    assert 'Reported response' in report
    assert 'not verified configuration compliance' in report
    # A differing executable config does not silently redefine the stated response.
    uptake = build_report_data(tmp_path)['runs'][0]['recommendation_uptake']
    assert uptake['followed'] == 1 and uptake['followed_fraction'] == 1
