"""The acceptance runner must never turn incomplete pytest evidence into a pass."""
import importlib
import json
from pathlib import Path
import sys

import pytest


def evaluator():
    assert importlib.util.find_spec('study.workshop_eval') is not None, 'workshop evaluation runner is missing'
    return importlib.import_module('study.workshop_eval')


def case(case_id, *nodes):
    return {'id': case_id, 'name': case_id, 'check': 'Fixture acceptance check.', 'pytest_nodes': list(nodes)}


def project(tmp_path, source, *, conftest=None, config=None):
    root = tmp_path / 'project'
    root.mkdir()
    (root / 'test_acceptance.py').write_text(source)
    if conftest:
        (root / 'conftest.py').write_text(conftest)
    if config:
        (root / 'pytest.ini').write_text(config)
    return root


def test_shared_parametrized_tests_execute_once_and_group_under_each_case(tmp_path):
    root = project(tmp_path, '''import pytest
from pathlib import Path
@pytest.mark.parametrize('value', ['first', 'second'])
def test_example(value):
    with Path('executions.txt').open('a') as handle:
        handle.write(value + '\\n')
    print('recorded ' + value)
''')
    output = tmp_path / 'results'
    result = evaluator().run_evaluation(output, project_root=root, cases=[
        case('normal', 'test_acceptance.py::test_example'),
        case('shared', 'test_acceptance.py::test_example'),
    ])
    assert result['passed'] is True
    assert [item['status'] for item in result['cases']] == ['passed', 'passed']
    assert [[row['node_id'] for row in item['tests']] for item in result['cases']] == [
        ['test_acceptance.py::test_example[first]', 'test_acceptance.py::test_example[second]'],
        ['test_acceptance.py::test_example[first]', 'test_acceptance.py::test_example[second]'],
    ]
    assert (root / 'executions.txt').read_text().splitlines() == ['first', 'second']
    assert result['command'][:3] == [sys.executable, '-m', 'pytest']
    assert json.loads((output / 'results.json').read_text()) == result
    assert (output / 'junit.xml').is_file()
    assert '2 passed' in (output / 'pytest.stdout.log').read_text()
    assert (output / 'pytest.stderr.log').is_file()


@pytest.mark.parametrize('outcome,body', [
    ('failed', "assert False, 'acceptance assertion failed'"),
    ('skipped', "pytest.skip('required check unavailable')"),
    ('error', "pass"),
])
def test_one_unsuccessful_parameter_fails_the_whole_named_case(tmp_path, outcome, body):
    fixture = "@pytest.fixture\ndef setup_check(request):\n    if request.param == 'bad':\n        raise RuntimeError('setup failed')\n    return request.param\n" if outcome == 'error' else ''
    marker = "@pytest.mark.parametrize('setup_check', ['good', 'bad'], indirect=True)\ndef test_example(setup_check):\n    value = setup_check" if outcome == 'error' else "@pytest.mark.parametrize('value', ['good', 'bad'])\ndef test_example(value):\n    pass"
    source = f"import pytest\n{fixture}{marker}\n    if value == 'bad':\n        {body}\n"
    root = project(tmp_path, source)
    result = evaluator().run_evaluation(tmp_path / 'results', project_root=root,
        cases=[case('required', 'test_acceptance.py::test_example')])
    assert result['passed'] is False
    assert result['cases'][0]['status'] == 'failed'
    assert [row['status'] for row in result['cases'][0]['tests']] == ['passed', outcome]


def test_deselected_mapped_test_fails_even_when_pytest_exits_zero(tmp_path):
    root = project(tmp_path, 'def test_present(): pass\ndef test_absent(): pass\n',
        config='[pytest]\naddopts = -k present\n')
    result = evaluator().run_evaluation(tmp_path / 'results', project_root=root, cases=[
        case('present', 'test_acceptance.py::test_present'),
        case('required', 'test_acceptance.py::test_absent'),
    ])
    assert result['pytest_exit_code'] == 0
    assert result['passed'] is False
    assert result['cases'][0]['status'] == 'passed'
    assert result['cases'][1]['missing_nodes'] == ['test_acceptance.py::test_absent']
    assert result['cases'][1]['status'] == 'failed'


def test_deselected_parameter_fails_even_when_its_sibling_passes(tmp_path):
    root = project(tmp_path, "import pytest\n@pytest.mark.parametrize('value', ['present', 'absent'])\ndef test_example(value): pass\n",
        config='[pytest]\naddopts = -k present\n')
    result = evaluator().run_evaluation(tmp_path / 'results', project_root=root,
        cases=[case('required', 'test_acceptance.py::test_example')])
    assert result['pytest_exit_code'] == 0
    assert result['passed'] is False
    assert result['cases'][0]['missing_nodes'] == ['test_acceptance.py::test_example[absent]']


def test_overlapping_function_and_parameter_selectors_do_not_repeat_a_test(tmp_path):
    root = project(tmp_path, """import pytest
from pathlib import Path
@pytest.mark.parametrize('value', ['first', 'second'])
def test_example(value):
    with Path('executions.txt').open('a') as handle:
        handle.write(value + '\\n')
""")
    result = evaluator().run_evaluation(tmp_path / 'results', project_root=root, cases=[
        case('all', 'test_acceptance.py::test_example'),
        case('one', 'test_acceptance.py::test_example[first]'),
    ])
    assert result['passed'] is True
    assert (root / 'executions.txt').read_text().splitlines() == ['first', 'second']
    assert len(result['cases'][1]['tests']) == 1


def test_inherited_pytest_addopts_cannot_silently_change_the_check_set(tmp_path, monkeypatch):
    root = project(tmp_path, 'def test_example(): pass\n')
    monkeypatch.setenv('PYTEST_ADDOPTS', '--collect-only')
    result = evaluator().run_evaluation(tmp_path / 'results', project_root=root,
        cases=[case('required', 'test_acceptance.py::test_example')])
    assert result['passed'] is True
    assert result['cases'][0]['tests'] == [{'node_id': 'test_acceptance.py::test_example', 'status': 'passed'}]


def test_nonzero_pytest_exit_fails_even_when_every_reported_test_passes(tmp_path):
    root = project(tmp_path, 'def test_example(): pass\n',
        conftest='def pytest_sessionfinish(session, exitstatus):\n    session.exitstatus = 3\n')
    result = evaluator().run_evaluation(tmp_path / 'results', project_root=root,
        cases=[case('required', 'test_acceptance.py::test_example')])
    assert result['cases'][0]['status'] == 'passed'
    assert result['pytest_exit_code'] == 3
    assert result['passed'] is False
    assert result['errors']


def test_timeout_saves_logs_and_a_failed_receipt_without_junit(tmp_path):
    root = project(tmp_path, 'import time\ndef test_example():\n    time.sleep(30)\n')
    output = tmp_path / 'results'
    result = evaluator().run_evaluation(output, project_root=root, timeout_seconds=.2,
        cases=[case('required', 'test_acceptance.py::test_example')])
    assert result['passed'] is False
    assert result['timed_out'] is True
    assert result['cases'][0]['status'] == 'failed'
    assert result['errors']
    assert json.loads((output / 'results.json').read_text())['timed_out'] is True
    assert (output / 'pytest.stdout.log').exists() and (output / 'pytest.stderr.log').exists()


def test_existing_evidence_is_not_reused_or_overwritten(tmp_path):
    root = project(tmp_path, 'def test_example(): pass\n')
    output = tmp_path / 'results'
    output.mkdir()
    (output / 'junit.xml').write_text('previous evidence')
    with pytest.raises(FileExistsError):
        evaluator().run_evaluation(output, project_root=root,
            cases=[case('required', 'test_acceptance.py::test_example')])
    assert (output / 'junit.xml').read_text() == 'previous evidence'


@pytest.mark.parametrize('timeout', [0, -1, float('nan'), float('inf')])
def test_invalid_timeout_is_rejected_before_creating_output(tmp_path, timeout):
    with pytest.raises(ValueError, match='timeout'):
        evaluator().run_evaluation(tmp_path / 'results', timeout_seconds=timeout)
    assert not (tmp_path / 'results').exists()


def test_unknown_case_is_rejected_before_creating_output(tmp_path):
    with pytest.raises(ValueError, match='Unknown case'):
        evaluator().run_evaluation(tmp_path / 'results', case_ids=['does-not-exist'])
    assert not (tmp_path / 'results').exists()
