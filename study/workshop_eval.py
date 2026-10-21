"""Run named, offline engineering acceptance checks with durable pytest evidence."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_PATH = Path(__file__).with_name('evaluation_cases.json')
ARTIFACTS = ('junit.xml', 'collected-nodes.json', 'pytest.stdout.log', 'pytest.stderr.log', 'results.json')
_COLLECTED_NODES = []


# These three hooks run only when the subprocess loads this module with -p.
# Capture before -k/-m deselection so passing siblings cannot hide missing cases.
def pytest_addoption(parser):
    parser.addoption('--workshop-collection', help='Save collected acceptance node IDs')


def pytest_itemcollected(item):
    _COLLECTED_NODES.append(item.nodeid)


def pytest_collection_finish(session):
    destination = session.config.getoption('--workshop-collection')
    if destination:
        Path(destination).write_text(json.dumps(_COLLECTED_NODES, indent=2) + '\n')


def load_cases() -> list[dict]:
    """Read the checked-in case-to-test mapping, without importing study runners."""
    manifest = json.loads(CASES_PATH.read_text())
    if manifest.get('schema_version') != 1:
        raise ValueError('Unsupported evaluation case schema')
    return manifest['cases']


def _selected_cases(cases, case_ids):
    if not isinstance(cases, list) or not cases:
        raise ValueError('At least one evaluation case is required')
    seen = set()
    for case in cases:
        if (not isinstance(case, dict) or not isinstance(case.get('id'), str)
                or not case['id'] or case['id'] in seen
                or not isinstance(case.get('pytest_nodes'), list) or not case['pytest_nodes']
                or any(not isinstance(node, str) or '::' not in node
                       for node in case['pytest_nodes'])):
            raise ValueError('Invalid or duplicate evaluation case')
        seen.add(case['id'])
    if case_ids is None:
        return cases
    unknown = set(case_ids) - seen
    if unknown:
        raise ValueError('Unknown case: ' + ', '.join(sorted(unknown)))
    selected = [case for case in cases if case['id'] in case_ids]
    if not selected:
        raise ValueError('At least one evaluation case is required')
    return selected


def _read_junit(path: Path) -> list[dict]:
    tests = []
    for item in ET.parse(path).getroot().iter('testcase'):
        filename = item.get('file', '').replace('\\', '/')
        module = filename.removesuffix('.py').replace('/', '.')
        classname = item.get('classname', '')
        classes = classname.removeprefix(module + '.').split('.') if classname != module else []
        # xunit1 includes file paths, including for parametrized function tests.
        node_id = '::'.join([filename, *classes, item.get('name', '')]) if filename else classname + '::' + item.get('name', '')
        status = 'passed'
        for tag, outcome in (('error', 'error'), ('failure', 'failed'), ('skipped', 'skipped')):
            if item.find(tag) is not None:
                status = outcome
                break
        tests.append({'node_id': node_id, 'status': status})
    return tests


def _matches(selector: str, node_id: str) -> bool:
    return node_id == selector or ('[' not in selector and node_id.startswith(selector + '['))


def run_evaluation(output: Path, *, case_ids=None, timeout_seconds: float = 300,
                   cases=None, project_root: Path = PROJECT_ROOT) -> dict:
    """Execute the union of selected nodes once and save all verdict evidence.

    ``cases`` and ``project_root`` allow local fixture projects to exercise this
    runner without running the scientific study or making model requests.
    """
    if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('Evaluation timeout must be finite and positive')
    selected = _selected_cases(load_cases() if cases is None else cases, case_ids)
    output = Path(output).resolve()
    project_root = Path(project_root).resolve()
    for filename in ARTIFACTS:
        if (output / filename).exists():
            raise FileExistsError(f'Existing evaluation evidence: {output / filename}')
    output.mkdir(parents=True, exist_ok=True)
    nodes = list(dict.fromkeys(node for case in selected for node in case['pytest_nodes']))
    command = [sys.executable, '-m', 'pytest', '-q', '-p', 'study.workshop_eval',
               f'--workshop-collection={output / "collected-nodes.json"}', '-o', 'junit_family=xunit1',
               f'--junitxml={output / "junit.xml"}', *nodes]
    environment = os.environ.copy()
    environment.pop('PYTEST_ADDOPTS', None)
    environment['PYTHONPATH'] = os.pathsep.join(filter(None, [str(PROJECT_ROOT), environment.get('PYTHONPATH')]))
    started_at = datetime.now(timezone.utc).isoformat()
    started = time.monotonic()
    errors = []
    timed_out = False
    exit_code = None
    with (output / 'pytest.stdout.log').open('w') as stdout, (output / 'pytest.stderr.log').open('w') as stderr:
        try:
            process = subprocess.Popen(command, cwd=project_root, stdout=stdout, stderr=stderr,
                                       env=environment, start_new_session=(os.name == 'posix'))
            try:
                exit_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                # Terminate pytest and any children sharing its process group.
                try:
                    if os.name == 'posix':
                        os.killpg(process.pid, signal.SIGKILL)
                    else:
                        process.kill()
                except ProcessLookupError:
                    pass
                exit_code = process.wait()
                errors.append(f'pytest exceeded the {timeout_seconds:g} second timeout')
        except OSError as exc:
            errors.append(f'Could not execute pytest: {exc}')
    if exit_code is not None and exit_code != 0:
        errors.append(f'pytest exited with status {exit_code}')
    try:
        tests = _read_junit(output / 'junit.xml')
    except (OSError, ET.ParseError) as exc:
        tests = []
        errors.append(f'Missing or invalid JUnit evidence: {exc}')
    try:
        collected = json.loads((output / 'collected-nodes.json').read_text())
        if not isinstance(collected, list) or any(not isinstance(node, str) for node in collected):
            raise ValueError('Expected a list of collected node IDs')
    except (OSError, ValueError) as exc:
        collected = []
        errors.append(f'Missing or invalid collection evidence: {exc}')
    verdicts = []
    for case in selected:
        matched = [test for test in tests if any(_matches(node, test['node_id']) for node in case['pytest_nodes'])]
        expected = list(dict.fromkeys(node for node in collected
                                     if any(_matches(selector, node) for selector in case['pytest_nodes'])))
        missing = [node for node in expected if not any(test['node_id'] == node for test in tests)]
        missing.extend(node for node in case['pytest_nodes']
                       if not any(_matches(node, item) for item in expected))
        verdicts.append({**case, 'status': 'passed' if not missing and all(test['status'] == 'passed' for test in matched) else 'failed',
                         'missing_nodes': missing, 'tests': matched})
    result = {
        'schema_version': 1,
        'kind': 'engineering_acceptance',
        'started_at': started_at,
        'elapsed_seconds': time.monotonic() - started,
        'passed': not errors and all(case['status'] == 'passed' for case in verdicts),
        'pytest_exit_code': exit_code,
        'timed_out': timed_out,
        'command': command,
        'project_root': str(project_root),
        'cases': verdicts,
        'errors': errors,
        'artifacts': {name: str(output / name) for name in ARTIFACTS},
    }
    (output / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Directory for fresh evaluation evidence')
    parser.add_argument('--case', action='append', dest='case_ids', help='Named case ID; repeat to select several (default: all)')
    parser.add_argument('--timeout', type=float, default=300, help='Whole pytest process timeout in seconds (default: 300)')
    args = parser.parse_args(argv)
    try:
        result = run_evaluation(args.output, case_ids=args.case_ids, timeout_seconds=args.timeout)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    passed = sum(case['status'] == 'passed' for case in result['cases'])
    print(json.dumps({'passed': result['passed'], 'cases_passed': passed,
                      'cases_total': len(result['cases']), 'results': result['artifacts']['results.json']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
