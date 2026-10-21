"""Budget trajectories use all runs and only a verified journal prefix."""
import json

import pytest

from study.report import build_report_data, generate_report
from test_report import write_run
from test_report_analysis import frozen_config


def evidence(scores, usages=None, roles=None):
    events = [{'type': 'run_started'}]
    for i, score in enumerate(scores, 1):
        usage = (usages[i-1] if usages else
                 {'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .1})
        role = roles[i-1] if roles else 'researcher'
        events += [{'type': 'model_call_started', 'role': role},
                   {'type': 'model_call', 'role': role, 'status': 'completed', 'usage': usage},
                   {'type': 'trial_started', 'trial_id': i},
                   {'type': 'trial_finished', 'result': {'trial_id': i,
                    'status': 'completed' if score is not None else 'failed',
                    'score': score, 'elapsed_seconds': i * 2}}]
    return events


def run(root, name='a', scores=(.5, .7, .9), *, condition='solo', events=None,
        objective=None, **changes):
    return write_run(root, name, events=events if events is not None else evidence(scores),
        condition=condition, repeat=0, problem_hash='problem', data_fingerprint='data',
        config=frozen_config(condition), accounting={},
        objective=objective or {'metric': 'accuracy', 'direction': 'maximize'},
        target_definitions=[], **changes)


def axis(root, name='tokens'):
    return build_report_data(root)['research_efficiency']['cohorts'][0]['axes'][name]


def test_exact_step_auc_common_budgets_and_discrete_experiments(tmp_path):
    run(tmp_path)
    run(tmp_path, 'b', (.6, .6, .8), condition='supervised')
    a = axis(tmp_path)
    assert (a['start'], a['budget']) == (10, 30)
    assert a['run_ids'] == ['a', 'b']
    solo = a['groups']['solo']
    assert solo['n'] == solo['total_runs'] == 1
    assert solo['quality'] == pytest.approx(.9)
    assert solo['baseline'] == pytest.approx(.5)
    assert solo['improvement'] == pytest.approx(.4)
    assert solo['mean_improvement_auc'] == pytest.approx(.1)
    assert a['per_run'][0]['improvement_area'] == pytest.approx(2)
    # Discrete mean is after attempts L+1..U, so the endpoint contributes.
    assert axis(tmp_path, 'experiments')['groups']['solo']['mean_improvement_auc'] == pytest.approx(.3)


@pytest.mark.parametrize('metric,scores,expected', [
    ('rmse', (4., 3., 2.), 2.), ('r2', (-4., -3., -2.), -2.)])
def test_objective_direction_and_unbounded_scores(tmp_path, metric, scores, expected):
    run(tmp_path, scores=scores, objective={'metric': metric,
        'direction': 'minimize' if metric == 'rmse' else 'maximize'})
    g = axis(tmp_path)['groups']['solo']
    assert g['quality'] == expected
    assert g['improvement'] == 2
    assert g['mean_improvement_auc'] == .5


def test_unknown_cost_does_not_discard_known_tokens_or_experiments(tmp_path):
    usages = [{'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .1},
              {'prompt_tokens': 8, 'completion_tokens': 2, 'cost': None},
              {'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .2}]
    run(tmp_path, events=evidence((.5, .7, .9), usages, ['researcher', 'supervisor', 'reflection']))
    data = build_report_data(tmp_path)
    curves = data['runs'][0]['resource_trajectories']
    assert curves['dollars']['end'] == pytest.approx(.1)
    assert len(curves['dollars']['points']) == 1
    assert curves['tokens']['end'] == 30
    assert axis(tmp_path, 'dollars')['status'] == 'no_shared_interval'
    assert axis(tmp_path)['groups']['solo']['quality'] == .9


def test_failed_trials_and_trailing_spend_count_without_quality_gain(tmp_path):
    events = evidence((.5, None, .7))
    events += [{'type': 'model_call_started', 'role': 'reviewer'},
               {'type': 'model_call', 'role': 'reviewer', 'status': 'failed',
                'usage': {'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .1}}]
    run(tmp_path, events=events)
    assert axis(tmp_path)['budget'] == 40
    assert axis(tmp_path)['groups']['solo']['mean_improvement_auc'] == pytest.approx(.2/3)
    assert axis(tmp_path, 'experiments')['budget'] == 3


def test_unfinished_call_censors_api_prefix_but_retains_trial_evidence(tmp_path):
    events = evidence((.5, .6)) + [{'type': 'model_call_started', 'role': 'supervisor'}]
    run(tmp_path, events=events, stop_reason='interrupted_unrecovered')
    data = build_report_data(tmp_path)
    curves = data['runs'][0]['resource_trajectories']
    assert curves['tokens']['end'] == 20
    assert 'unfinished' in curves['tokens']['reason']
    assert axis(tmp_path)['groups']['solo']['quality'] == .6


def test_missing_baseline_blocks_full_cohort_instead_of_selecting_successes(tmp_path):
    run(tmp_path)
    run(tmp_path, 'failed', (None, None), condition='supervised')
    a = axis(tmp_path)
    assert a['status'] == 'missing_evidence'
    assert a['run_ids'] == ['a', 'failed']
    assert a['unavailable_runs'] == ['failed']
    assert a['groups'] == {}
    assert 'failed' in json.dumps(build_report_data(tmp_path)['research_efficiency'])


def test_no_extrapolation_and_fixed_cohort_across_axes(tmp_path):
    run(tmp_path)
    run(tmp_path, 'b', (.6, .8), condition='supervised')
    data = build_report_data(tmp_path)['research_efficiency']
    for a in data['cohorts'][0]['axes'].values():
        assert a['run_ids'] == ['a', 'b']
    assert axis(tmp_path)['budget'] == 20
    assert axis(tmp_path)['groups']['solo']['quality'] == .7


def test_unknown_identity_is_explicit_and_distinct_configs_never_pool(tmp_path):
    p = run(tmp_path)
    run(tmp_path, 'b', condition='supervised')
    s = json.loads((p / 'summary.json').read_text())
    s['config']['max_tokens'] = 99
    (p / 'summary.json').write_text(json.dumps(s))
    data = build_report_data(tmp_path)['research_efficiency']
    assert len(data['cohorts']) == 2
    s['config'] = {}
    (p / 'summary.json').write_text(json.dumps(s))
    assert build_report_data(tmp_path)['research_efficiency']['excluded_runs'][0]['run_id'] == 'a'


def test_corrupt_journal_never_becomes_zero_spend(tmp_path):
    p = run(tmp_path)
    with (p / 'events.jsonl').open('a') as f:
        f.write('{broken}\n')
    assert axis(tmp_path)['status'] == 'missing_evidence'


def test_summary_is_deterministic_factual_and_exported_with_supporting_details(tmp_path):
    run(tmp_path)
    run(tmp_path, 'b', (.6, .6, .8), condition='supervised')
    data = build_report_data(tmp_path)['research_efficiency']
    assert data == build_report_data(tmp_path)['research_efficiency']
    text = '\n'.join(data['summary'])
    assert 'solo' in text and '30' in text and 'descriptive' in text
    assert 'not evidence of strategy superiority' in text
    output = generate_report(tmp_path)
    html = output.read_text()
    assert html.index('Research efficiency') < html.index('Declared outcome')
    assert '<details><summary>Supporting evidence' in html
    assert (tmp_path / 'research-efficiency.json').exists()
    assert (tmp_path / 'report-summary.txt').read_text().strip() == text
    assert (tmp_path / 'figures/efficiency-1.png').exists()


def test_out_of_place_generation_keeps_all_source_bytes_and_records_hashes(tmp_path):
    from hashlib import sha256
    source, output = tmp_path / 'source', tmp_path / 'new-report'
    run(source)
    (source / 'report.html').write_text('historical report')
    before = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    assert generate_report(source, destination=output) == output / 'report.html'
    after = {str(p.relative_to(source)): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    assert after == before
    provenance = json.loads((output / 'report-provenance.json').read_text())
    assert provenance['source'] == str(source.resolve())
    assert provenance['sha256']['runs/a/events.jsonl'] == sha256(before['runs/a/events.jsonl']).hexdigest()
    assert 'report.html' not in provenance['sha256']


def test_cli_separate_destination_is_read_only_for_source(tmp_path, monkeypatch, capsys):
    from study.__main__ import main
    run(tmp_path / 'source')
    monkeypatch.setattr('sys.argv', ['study', 'report', '--output', str(tmp_path / 'source'),
                                   '--report-dir', str(tmp_path / 'rendered')])
    main()
    assert not (tmp_path / 'source/postrun.json').exists()
    assert (tmp_path / 'rendered/report.html').exists()


def test_unknown_tokens_censor_only_tokens_and_known_subsets_are_not_added_twice(tmp_path):
    usages = [{'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .1,
               'prompt_tokens_details': {'cached_tokens': 5},
               'completion_tokens_details': {'reasoning_tokens': 2}},
              {'prompt_tokens': None, 'completion_tokens': 2, 'cost': .1}]
    run(tmp_path, events=evidence((.5, .8), usages))
    assert axis(tmp_path)['status'] == 'no_shared_interval'
    assert axis(tmp_path, 'dollars')['groups']['solo']['quality'] == .8
    assert axis(tmp_path, 'experiments')['groups']['solo']['quality'] == .8


def test_complete_snapshot_disagreement_never_credits_a_low_budget(tmp_path):
    events = evidence((.5, .8))
    events[2]['accounting'] = {'cost_complete': True, 'known_cost': 100}
    run(tmp_path, events=events)
    assert axis(tmp_path, 'dollars')['status'] == 'missing_evidence'
    assert axis(tmp_path)['groups']['solo']['quality'] == .8


def test_incomplete_suite_keeps_unstarted_run_in_efficiency_cohort(tmp_path):
    run(tmp_path)
    summary = json.loads((tmp_path / 'runs/a/summary.json').read_text())
    manifest = {k: summary[k] for k in ('objective', 'problem_hash', 'data_fingerprint', 'target_definitions')}
    manifest.update(config=summary['config'], schedule=[
        {'run_id': 'a', 'condition': 'solo', 'repeat': 0},
        {'run_id': 'missing', 'condition': 'supervised', 'repeat': 0}])
    (tmp_path / 'suite.json').write_text(json.dumps(manifest))
    a = axis(tmp_path)
    assert a['run_ids'] == ['a', 'missing']
    assert a['unavailable_runs'] == ['missing']
    assert a['groups'] == {}


def test_zero_usage_ties_and_endpoint_jumps_have_exact_integrals(tmp_path):
    # A free second call updates the incumbent at the same budget as the first.
    run(tmp_path, events=evidence((.5, .7, .9), [
        {'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .1},
        {'prompt_tokens': 0, 'completion_tokens': 0, 'cost': 0},
        {'prompt_tokens': 8, 'completion_tokens': 2, 'cost': .1}]))
    g = axis(tmp_path)['groups']['solo']
    assert g['baseline'] == .7
    assert g['quality'] == .9
    assert g['mean_improvement_auc'] == 0


def test_unfinished_trial_is_an_attempt_without_an_invented_score(tmp_path):
    events = evidence((.5, .7)) + [{'type': 'trial_started', 'trial_id': 3}]
    p = run(tmp_path, events=events)
    summary = json.loads((p / 'summary.json').read_text())
    summary['trials'] = 3
    (p / 'summary.json').write_text(json.dumps(summary))
    a = axis(tmp_path, 'experiments')
    assert a['budget'] == 3
    assert a['groups']['solo']['quality'] == .7
    assert a['groups']['solo']['mean_improvement_auc'] == pytest.approx(.2)


def test_duplicate_result_cannot_leak_future_quality_into_past_budget(tmp_path):
    events = evidence((.5, .7))
    events.append({'type': 'trial_finished', 'result': {'trial_id': 1, 'status': 'completed',
                                                      'score': .99, 'elapsed_seconds': 6}})
    run(tmp_path, events=events)
    curves = build_report_data(tmp_path)['runs'][0]['resource_trajectories']
    for c in curves.values():
        assert [p['quality'] for p in c['points']] == [.5, .7]
        assert 'duplicate' in c['reason']


@pytest.mark.parametrize('flag,axis_name', [('cost_complete', 'dollars'), ('token_usage_complete', 'tokens')])
def test_explicit_incomplete_call_snapshot_censors_that_axis(tmp_path, flag, axis_name):
    events = evidence((.5, .7))
    events[2]['accounting'] = {flag: False}
    run(tmp_path, events=events)
    assert axis(tmp_path, axis_name)['status'] == 'missing_evidence'
    other = 'tokens' if axis_name == 'dollars' else 'dollars'
    assert axis(tmp_path, other)['status'] == 'available'


@pytest.mark.parametrize('flag,axis_name', [('cost_complete', 'dollars'), ('token_usage_complete', 'tokens')])
def test_unlocated_summary_accounting_gap_is_not_overridden(tmp_path, flag, axis_name):
    p = run(tmp_path)
    s = json.loads((p/'summary.json').read_text())
    s['accounting'] = {flag: False}
    (p/'summary.json').write_text(json.dumps(s))
    assert axis(tmp_path, axis_name)['status'] == 'missing_evidence'


def test_missing_trial_start_cannot_be_silently_skipped_in_resource_history(tmp_path):
    events = evidence((.5, .7))
    events = [e for e in events if not (e['type']=='trial_started' and e['trial_id']==1)]
    run(tmp_path, events=events)
    assert axis(tmp_path)['status'] == 'missing_evidence'


def test_malformed_trial_start_is_an_evidence_limit_not_a_report_crash(tmp_path):
    p = run(tmp_path)
    with (p/'events.jsonl').open('a') as f:
        f.write(json.dumps({'type': 'trial_started', 'trial_id': [4]}) + '\n')
    data = build_report_data(tmp_path)
    assert all(c['reason'] for c in data['runs'][0]['resource_trajectories'].values())


def test_duplicate_run_start_invalidates_unknown_journal_boundary(tmp_path):
    events = evidence((.5, .7)) + [{'type': 'run_started'}]
    run(tmp_path, events=events)
    assert axis(tmp_path)['status'] == 'missing_evidence'


def test_trial_evidence_limit_does_not_locate_a_summary_spending_gap(tmp_path):
    events = evidence((.5, .7))
    events.append({'type': 'trial_finished', 'result': {'trial_id': 1, 'status': 'completed',
                                                      'score': .99, 'elapsed_seconds': 6}})
    p = run(tmp_path, events=events)
    s = json.loads((p/'summary.json').read_text())
    s['accounting'] = {'cost_complete': False}
    (p/'summary.json').write_text(json.dumps(s))
    assert axis(tmp_path, 'dollars')['status'] == 'missing_evidence'
    assert axis(tmp_path)['status'] == 'available'


def test_malformed_call_accounting_is_an_explicit_limit(tmp_path):
    events = evidence((.5, .7))
    events[2]['accounting'] = ['invalid snapshot']
    run(tmp_path, events=events)
    assert axis(tmp_path)['status'] == 'missing_evidence'
    assert axis(tmp_path, 'experiments')['status'] == 'available'
