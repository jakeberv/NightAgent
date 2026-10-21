"""Strategy efficiency must retain nonattainers and unknown accounting."""
import json

from study.report import build_report_data, generate_report


METADATA = {'objective': {'metric': 'accuracy', 'direction': 'maximize'},
            'problem_hash': 'efficiency-problem', 'problem': {'id': 'efficiency-problem'},
            'target_definitions': [{'name': 'useful', 'value': .9}]}


def account(cost, tokens, *, complete=True):
    return {'known_cost': cost, 'cost_complete': complete, 'token_usage_complete': complete,
            'input_tokens': tokens, 'output_tokens': 0}


def write_run(root, identity, *, reached=False, seconds=10, end_seconds=30,
              crossing=None, ending=None, condition='researcher_alone', repeat=0):
    folder = root / 'runs' / identity
    folder.mkdir(parents=True)
    trial = {'trial_id': 1, 'status': 'completed', 'elapsed_seconds': seconds,
             'score': .95 if reached else .8, 'metrics': {'accuracy': .95 if reached else .8}}
    selected = {**trial, 'accounting': crossing or {}}
    summary = {**METADATA, 'run_id': identity, 'condition': condition, 'repeat': repeat,
               'config': {'allowance_seconds': 100}, 'allowance_seconds': 100,
               'elapsed_seconds': end_seconds, 'stop_reason': 'trial_cap', 'trials': 1,
               'best': selected, 'target_selections': {'useful': selected if reached else None},
               'accounting': ending or {}}
    (folder / 'summary.json').write_text(json.dumps(summary))
    (folder / 'events.jsonl').write_text(json.dumps({'type': 'trial_finished', 'result': trial}) + '\n')
    return folder


def mixed_suite(root):
    write_run(root, 'hit', reached=True, crossing=account(.2, 100), ending=account(.5, 300))
    write_run(root, 'unbilled-hit', reached=True, seconds=20, end_seconds=50,
              crossing=account(.3, 150, complete=False), ending=account(.6, 600, complete=False), repeat=1)
    write_run(root, 'miss', end_seconds=40, ending=account(.4, 500), repeat=2)
    write_run(root, 'unbilled-miss', end_seconds=25, ending=account(.1, 80, complete=False), repeat=3)
    (root / 'suite.json').write_text(json.dumps({**METADATA, 'config': {'allowance_seconds': 100},
        'schedule': [{'run_id': name, 'condition': 'researcher_alone', 'repeat': index}
                     for index, name in enumerate(('hit', 'unbilled-hit', 'miss', 'unbilled-miss', 'not-started'))]}))


def test_target_summaries_are_conditional_and_misses_keep_observed_end_budgets(tmp_path):
    mixed_suite(tmp_path)
    details = build_report_data(tmp_path)['conditions']['researcher_alone']['targets']['useful']
    assert (details['n'], details['reached'], details['not_reached'], details['fraction']) == (5, 2, 3, .4)
    conditional = details['conditional_at_attainment']
    assert conditional['seconds']['n'] == 2
    assert conditional['seconds']['mean'] == 15
    assert conditional['total_cost'] == {'n': 1, 'missing': 1, 'mean': .2, 'sd': None, 'min': .2, 'max': .2}
    assert conditional['total_tokens']['mean'] == 100
    misses = {row['run_id']: row for row in details['nonattainment']['observed_end_budgets']}
    assert misses['miss']['seconds'] == 40
    assert misses['miss']['total_cost'] == .4
    assert misses['miss']['total_tokens'] == 500
    assert misses['unbilled-miss']['known_cost'] == .1
    assert misses['unbilled-miss']['total_cost'] is None
    assert misses['not-started']['seconds'] is None
    assert misses['not-started']['total_cost'] is None


def test_budget_curves_keep_all_runs_and_identify_incomplete_accounting(tmp_path):
    mixed_suite(tmp_path)
    details = build_report_data(tmp_path)['conditions']['researcher_alone']['targets']['useful']
    cost = details['attainment_by_budget']['total_cost']
    assert cost['denominator'] == 5
    assert cost['curve'] == [(0., 0.), (.2, .2), (.4, .2)]
    assert cost['reached_with_unknown_budget'] == ['unbilled-hit']
    assert set(cost['not_reached_with_unknown_end_budget']) == {'unbilled-miss', 'not-started'}
    assert cost['censored'] == [{'run_id': 'miss', 'budget': .4}]
    tokens = details['attainment_by_budget']['total_tokens']
    assert tokens['curve'] == [(0., 0.), (100., .2), (500., .2)]
    seconds = details['attainment_by_budget']['seconds']
    assert seconds['curve'] == [(0., 0.), (10., .2), (20., .4), (40., .4)]
    assert seconds['curve'][-1][0] < 100  # No extrapolation to the scheduled allowance.


def test_no_attainment_does_not_invent_crossing_cost_or_time(tmp_path):
    write_run(tmp_path, 'miss', end_seconds=17, ending=account(0, 0))
    details = build_report_data(tmp_path)['conditions']['researcher_alone']['targets']['useful']
    assert details['reached'] == 0 and details['not_reached'] == 1
    assert details['conditional_at_attainment']['seconds']['mean'] is None
    assert details['conditional_at_attainment']['total_cost']['n'] == 0
    assert details['attainment_by_budget']['total_cost']['curve'] == [(0., 0.)]
    assert details['attainment_by_budget']['seconds']['curve'] == [(0., 0.), (17., 0.)]


def test_first_crossing_budget_does_not_use_accounting_from_a_later_selection(tmp_path):
    folder = write_run(tmp_path, 'hit', reached=True, crossing=account(.8, 400), ending=account(1, 500))
    summary = json.loads((folder / 'summary.json').read_text())
    event = json.loads((folder / 'events.jsonl').read_text())
    event['result']['accounting'] = account(.2, 100)
    (folder / 'events.jsonl').write_text(json.dumps(event) + '\n')
    summary['target_selections']['useful'].update(trial_id=2, elapsed_seconds=20)
    summary['best'] = summary['target_selections']['useful']
    (folder / 'summary.json').write_text(json.dumps(summary))
    details = build_report_data(tmp_path)['runs'][0]['targets']['useful']
    assert details['seconds'] == 10
    assert details['total_cost'] == .2 and details['total_tokens'] == 100
    del event['result']['accounting']
    (folder / 'events.jsonl').write_text(json.dumps(event) + '\n')
    (folder / 'summary.json').write_text(json.dumps(summary))
    details = build_report_data(tmp_path)['runs'][0]['targets']['useful']
    assert details['total_cost'] is None and details['total_tokens'] is None


def test_html_displays_censoring_and_conditional_limits_with_exported_efficiency_data(tmp_path):
    write_run(tmp_path, 'hit', reached=True, crossing=account(.2, 100), ending=account(.5, 300))
    output = generate_report(tmp_path)
    document = output.read_text()
    assert 'Strategy efficiency at preset targets' in document
    assert 'Conditional on reaching the target' in document
    assert 'not an overall strategy efficiency estimate' in document
    assert 'censored at their observed end budgets' in document
    assert 'single repeat cannot establish a strategy ranking' in document
    exported = json.loads((tmp_path / 'strategy-efficiency.json').read_text())
    assert exported['researcher_alone']['useful']['n'] == 1
    assert (tmp_path / 'figures' / 'target-budgets.svg').exists()
