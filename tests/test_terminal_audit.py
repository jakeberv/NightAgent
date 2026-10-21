"""Only explicit, terminal deadline abandonment can excuse an invalid review."""
from copy import deepcopy

import pytest

from test_audit import recorded_suite, suite, audit as run_audit, codes, events, save_events, read, write
from study.report import build_report_data


def audit(root):
    report = build_report_data(root)
    write(root/'paired-comparisons.json', report['paired_comparisons'])
    write(root/'strategy-efficiency.json', {n: v['targets'] for n, v in report['conditions'].items()})
    return run_audit(root)


def terminal_chain(suite):
    run = suite/'runs/r00-periodic_reflection'
    es = events(run)
    template = next(e for e in es if e['type'] == 'reflection_contract')
    invalid = {**deepcopy(template), 'after_trial': 7, 'valid': False,
               'errors': ['lesson summary exceeds 240 characters']}
    skipped = {'type': 'model_call_skipped', 'role': 'reflection',
               'reason': 'deadline_admission', 'remaining_seconds': 10., 'required_seconds': 20.}
    abandoned = {'type': 'contract_abandoned', 'role': 'reflection', 'stage': 'review',
                 'after_trial': 7, 'reason': 'deadline_admission',
                 'contract': invalid['contract'], 'errors': invalid['errors']}
    summary = read(run/'summary.json'); summary['stop_reason'] = 'deadline'
    write(run/'summary.json', summary)
    es[-1]['summary'] = summary
    es[-1:-1] = [invalid, skipped, abandoned]
    return run, es


def test_explicit_terminal_review_abandonment_warns_without_accepting_it(suite):
    run, es = terminal_chain(suite); save_events(run, es)
    result = audit(suite)
    assert result['passed'], result
    assert any(w['code'] == 'contract_abandoned' and w['scope'] == run.name
               for w in result['warnings'])
    assert 'contract_unrepaired' not in codes(result)


@pytest.mark.parametrize('mutation', [
    'no_marker', 'no_skip', 'wrong_role', 'wrong_stage', 'wrong_trial',
    'wrong_contract', 'wrong_errors', 'wrong_reason', 'not_deadline',
    'budget_fits', 'budget_boolean', 'late_call', 'late_delivery',
    'accepted_after', 'orphan_marker', 'duplicate_marker',
])
def test_abandonment_cannot_hide_invalid_or_nonterminal_contracts(suite, mutation):
    run, es = terminal_chain(suite)
    marker = es[-2]; skip = es[-3]
    if mutation == 'no_marker': es.pop(-2)
    elif mutation == 'no_skip': es.pop(-3)
    elif mutation == 'wrong_role': marker['role'] = 'researcher'
    elif mutation == 'wrong_stage': marker['stage'] = 'framing'
    elif mutation == 'wrong_trial': marker['after_trial'] = 6
    elif mutation == 'wrong_contract': marker['contract'] = {'summary': 'other'}
    elif mutation == 'wrong_errors': marker['errors'] = ['different error']
    elif mutation == 'wrong_reason': marker['reason'] = 'invalid_contract'
    elif mutation == 'not_deadline':
        summary = read(run/'summary.json'); summary['stop_reason'] = 'trial_cap'
        write(run/'summary.json', summary); es[-1]['summary'] = summary
    elif mutation == 'budget_fits': skip['remaining_seconds'] = 30.
    elif mutation == 'budget_boolean': skip['required_seconds'] = True
    elif mutation == 'late_call':
        es.insert(-1, deepcopy(next(e for e in es if e['type'] == 'model_call_started')))
    elif mutation == 'late_delivery':
        es.insert(-1, deepcopy(next(e for e in es if e['type'] == 'lesson_memory')))
    elif mutation == 'accepted_after':
        accepted = deepcopy(es[-4]); accepted.update(valid=True, errors=[])
        es.insert(-1, accepted)
    elif mutation == 'orphan_marker': es.pop(-4)
    elif mutation == 'duplicate_marker': es.insert(-1, deepcopy(marker))
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'], result
    assert codes(result) & {'contract_abandoned', 'contract_unrepaired'}, result


def failed_repairs(es, *, count=1, role='reflection', status='failed', known_usage=True):
    """Insert paid repair failures between the rejected contract and skipped retry."""
    import json
    from study.events import Accounting
    from study.run_context import compact_lessons
    request = deepcopy(next(e for e in reversed(es) if e['type'] == 'model_call_started'))
    context = json.loads(request['messages'][1]['content'])
    context['lessons'] = compact_lessons(next(e for e in reversed(es) if e['type'] == 'lesson_memory')['lessons'])
    request['messages'][1]['content'] = json.dumps(context)
    usage = {'cost': .01, 'prompt_tokens': 1, 'completion_tokens': 1,
             'prompt_tokens_details': {'cached_tokens': 0},
             'completion_tokens_details': {'reasoning_tokens': 0}} if known_usage else None
    records = []
    for attempt in range(count):
        records.extend([{**deepcopy(request), 'role': role, 'attempt': attempt},
                        {'type': 'model_call', 'role': role, 'attempt': attempt,
                         'status': status, 'usage': usage, 'duration_seconds': .01}])
    es[-3:-3] = records
    accounting = Accounting()
    for event in es:
        if event['type'] == 'model_call': accounting.add(event.get('usage'))
    es[-1]['summary']['accounting'] = accounting.snapshot()


def test_accounted_failed_repair_followed_by_skipped_retry_can_be_abandoned(suite):
    run, es = terminal_chain(suite); failed_repairs(es)
    write(run/'summary.json', es[-1]['summary']); save_events(run, es)
    result = audit(suite)
    assert result['passed'], result
    assert any(w['code'] == 'contract_abandoned' for w in result['warnings'])
    assert any(w['code'] == 'model_call' for w in result['warnings'])


@pytest.mark.parametrize('mutation', [
    'successful_repair', 'unrelated_role', 'unknown_billing', 'unrelated_activity',
    'wrong_attempt', 'excess_retries',
])
def test_failed_repair_exception_cannot_hide_other_activity(suite, mutation):
    run, es = terminal_chain(suite)
    failed_repairs(es, count=2 if mutation == 'excess_retries' else 1,
                   role='researcher' if mutation == 'unrelated_role' else 'reflection',
                   status='completed' if mutation == 'successful_repair' else 'failed',
                   known_usage=mutation != 'unknown_billing')
    if mutation == 'unrelated_activity':
        es.insert(-3, {'type': 'tool_call', 'role': 'reflection', 'name': 'other', 'result': {}})
    elif mutation == 'wrong_attempt': es[-5]['attempt'] = es[-4]['attempt'] = 1
    write(run/'summary.json', es[-1]['summary']); save_events(run, es)
    result = audit(suite)
    assert not result['passed'], result
    assert codes(result) & {'contract_abandoned', 'contract_unrepaired'}, result


@pytest.mark.parametrize('field', ['remaining_seconds', 'required_seconds'])
@pytest.mark.parametrize('sign', [-1, 1])
def test_oversized_abandonment_budget_fails_without_crashing(suite, field, sign):
    run, es = terminal_chain(suite); es[-3][field] = sign * 10**1000
    save_events(run, es)
    result = audit(suite)
    assert not result['passed']
    assert 'contract_abandoned' in codes(result)
