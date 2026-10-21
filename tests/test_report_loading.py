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
