"""Current report evidence and output publication contracts."""
import json

import pytest

from study.report import build_report_data, generate_report


def write_current_run(root):
    root.mkdir(parents=True, exist_ok=True)
    result = {'trial_id': 1, 'status': 'completed', 'elapsed_seconds': 8,
              'duration_seconds': 2, 'training_seconds': 2,
              'score': .8, 'metrics': {'accuracy': .8}}
    summary = {'run_id': 'current', 'condition': 'researcher_alone', 'repeat': 0,
               'config': {'decision_protocol': 'structured_v1'}, 'trials': 2,
               'objective': {'metric': 'accuracy', 'direction': 'maximize'},
               'target_definitions': [{'name': 'useful', 'value': .9}],
               'allowance_seconds': 100, 'elapsed_seconds': 20,
               'stop_reason': 'trial_cap', 'best': None, 'target_selections': {}}
    (root / 'summary.json').write_text(json.dumps(summary))
    (root / 'events.jsonl').write_text(json.dumps(
        {'type': 'trial_finished', 'elapsed_seconds': 9, 'result': result}) + '\n')
    return summary, result


def test_corrupt_event_cannot_be_reconstructed_from_a_frozen_selection(tmp_path):
    summary, result = write_current_run(tmp_path)
    selected = {**result, 'trial_id': 2, 'score': .99, 'metrics': {'accuracy': .99}}
    summary.update(best=selected, target_selections={'useful': selected})
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    with (tmp_path / 'events.jsonl').open('a') as handle:
        handle.write('{"type":"trial_finished","result":')
    data = build_report_data(tmp_path)
    row, = data['runs']
    assert row['best_score'] == .8
    assert row['targets']['useful']['reached'] is False
    assert row['trial_attempts'] == 2
    assert row['trial_outcomes']['Other / unknown'] == 1
    assert any('events.jsonl' in warning and '2' in warning for warning in data['warnings'])


def test_report_requires_the_frozen_objective_instead_of_guessing_roc_auc(tmp_path):
    summary, _ = write_current_run(tmp_path)
    del summary['objective']
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='objective'):
        build_report_data(tmp_path)


def test_render_failure_preserves_the_previous_published_report(tmp_path, monkeypatch):
    import study.report_graphics as graphics
    summary, _ = write_current_run(tmp_path)
    generate_report(tmp_path)
    summary['elapsed_seconds'] = 42
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    old_outputs = {path.relative_to(tmp_path): path.read_bytes()
                   for path in tmp_path.rglob('*') if path.is_file()}
    def broken_export(*args, **kwargs):
        raise RuntimeError('render interrupted')
    monkeypatch.setattr(graphics, 'export_figure', broken_export)
    with pytest.raises(RuntimeError, match='render interrupted'):
        generate_report(tmp_path)
    assert all((tmp_path / name).read_bytes() == value for name, value in old_outputs.items())


def test_missing_trial_evidence_is_unknown_even_when_summary_selects_a_model(tmp_path):
    summary, result = write_current_run(tmp_path)
    summary.update(best=result, target_selections={'useful': result})
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    (tmp_path / 'events.jsonl').unlink()
    data = build_report_data(tmp_path)
    row, = data['runs']
    assert row['best_score'] is None
    assert row['trial_outcomes']['Other / unknown'] == 2
    assert any('trial' in warning.lower() and 'evidence' in warning.lower()
               for warning in data['warnings'])


@pytest.mark.parametrize('metric', ['accuracy', 'roc_auc'])
@pytest.mark.parametrize('threshold', [.75, .9])
def test_heldout_scores_require_the_observed_selected_artifact(tmp_path, metric, threshold):
    summary, result = write_current_run(tmp_path)
    summary.update(objective={'metric': metric, 'direction': 'maximize'},
                   target_definitions=[{'name': 'stretch', 'value': threshold}])
    result.update(artifact_hash='observed-artifact', metrics={metric: .8})
    selected = {**result, 'trial_id': 2, 'score': .99,
                'artifact_hash': 'missing-artifact', 'metrics': {metric: .99}}
    summary.update(best=selected, target_selections={'stretch': selected})
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    (tmp_path / 'events.jsonl').write_text(json.dumps(
        {'type': 'trial_finished', 'result': result}) + '\n')
    (tmp_path / 'test-results.json').write_text(json.dumps({'selections': {
        name: {'status': 'completed', 'artifact_hash': 'missing-artifact',
               'score': .97, 'metrics': {metric: .97}} for name in ('best', 'stretch')}}))
    data = build_report_data(tmp_path)
    row, = data['runs']
    assert row['best_score'] == .8
    assert row['best_test_score'] is None and row['best_test_metrics'] == {}
    assert row['targets']['stretch']['test_score'] is None
    assert row['targets']['stretch']['test_metrics'] == {}
    if metric == 'roc_auc':
        assert row['best_test_auc'] is None and row['stretch_test_auc'] is None
    assert any('held-out' in warning.lower() and 'artifact' in warning.lower()
               for warning in data['warnings'])


@pytest.mark.parametrize('definitions', [None, {}, 'missing'])
def test_report_rejects_missing_or_nonlist_frozen_target_definitions(tmp_path, definitions):
    summary, _ = write_current_run(tmp_path)
    if definitions == 'missing':
        summary.pop('target_definitions')
    else:
        summary['target_definitions'] = definitions
    (tmp_path / 'summary.json').write_text(json.dumps(summary))
    with pytest.raises(ValueError, match='target_definitions'):
        build_report_data(tmp_path)
