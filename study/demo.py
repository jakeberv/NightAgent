"""Build an offline workshop replay from audited, frozen study evidence.

This module reads JSON and hashes artifacts. It never unpickles models, fits an
estimator, constructs a provider, or requests credentials.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .audit import audit_suite
from .records import load_events
from .report_data import build_report_data
from .run_context import compact_lessons


def _digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def _read(path):
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(value, dict):
        raise ValueError(f'{Path(path).name} must contain a JSON object')
    return value


def _changes(before, after):
    def fields(config):
        return {**{key: value for key, value in config.items() if key != 'params'},
                **{'params.' + key: value for key, value in config.get('params', {}).items()}}
    left, right = fields(before), fields(after)
    return [{'field': key, 'before': left.get(key), 'after': right.get(key)}
            for key in sorted(left.keys() | right.keys()) if left.get(key) != right.get(key)]


def _measurement(event):
    result = event['result']
    return {key: result[key] for key in ('trial_id', 'config', 'score', 'metrics', 'seed',
                                        'elapsed_seconds', 'artifact_hash') if key in result}


def _chain(events, journal):
    """Choose by evidence coverage and chronological order, never by score."""
    fits = {e['result']['trial_id']: (i, e) for i, e in enumerate(events) if e['type'] == 'trial_finished'}
    def source(index):
        return {'path': journal, 'line': index + 1, 'type': events[index]['type']}
    for index, event in enumerate(events):
        contract = event.get('contract', {})
        baseline_id, trial_id = contract.get('baseline_trial_id'), event.get('trial_id')
        if event['type'] != 'decision_contract' or not event.get('valid') or not event.get('executed'):
            continue
        if baseline_id not in fits or trial_id not in fits:
            continue
        baseline_index, baseline = fits[baseline_id]
        result_index, result = fits[trial_id]
        if not baseline_index < index < result_index:
            continue
        changes = _changes(baseline['result']['config'], result['result']['config'])
        if not changes:
            continue
        for lesson_index in range(result_index + 1, len(events)):
            memory = events[lesson_index]
            if memory['type'] != 'lesson_memory':
                continue
            for lesson in memory['lessons']:
                if not {baseline_id, trial_id}.issubset({e['trial_id'] for e in lesson['evidence']}):
                    continue
                compact, = compact_lessons([lesson])
                for delivery_index in range(lesson_index + 1, len(events)):
                    delivery = events[delivery_index]
                    if delivery['type'] != 'model_call_started' or delivery['role'] != 'researcher':
                        continue
                    context = json.loads(delivery['messages'][1]['content'])
                    if compact not in context.get('lessons', []):
                        continue
                    advice_index = next((i for i in range(index - 1, -1, -1)
                                         if events[i]['type'] in ('framing', 'review')), None)
                    reflection_index = next((i for i in range(index - 1, -1, -1)
                                             if events[i]['type'] == 'reflection'), None)
                    if advice_index is None or reflection_index is None:
                        continue
                    advice, reflection = events[advice_index], events[reflection_index]
                    return {'selection_rule': 'First chronological executed comparison whose baseline and result are cited together in a later lesson delivered to a researcher.',
                        'recommendation': {'text': advice['contract']['recommendation'],
                                           'after_trial': advice['after_trial'], 'source': source(advice_index)},
                        'reflection': {'text': reflection['contract']['next_comparison'],
                                       'after_trial': reflection['after_trial'], 'source': source(reflection_index)},
                        'decision': {**contract, 'source': source(index)},
                        'baseline': {**_measurement(baseline), 'source': source(baseline_index)},
                        'changes': changes,
                        'result': {**_measurement(result), 'source': source(result_index)},
                        'score_delta': result['result']['score'] - baseline['result']['score'],
                        'lesson': {**compact, 'interpretation_status': lesson.get('interpretation', {}).get('status', 'unverified'),
                                   'elapsed_seconds': memory['elapsed_seconds'], 'source': source(lesson_index)},
                        'delivery': {'role': 'researcher', 'before_trial_id': context['trials_attempted'] + 1,
                                     'elapsed_seconds': delivery['elapsed_seconds'],
                                     'lesson_ids': [item['id'] for item in context['lessons']],
                                     'delivered_lesson': compact, 'source': source(delivery_index)}}
    raise ValueError('No complete decision, measurement, scoped lesson, and later context delivery chain exists')


def _reference(path, report, suite):
    path = Path(path).resolve()
    if path.is_relative_to(suite):
        raise ValueError('Fixed reference evidence must be separate from the adaptive suite')
    result = _read(path)
    provenance = result.get('provenance', {})
    if any(not report.get(key) or provenance.get(key) != report[key]
           for key in ('problem_hash', 'data_fingerprint')):
        raise ValueError('Reference identity differs from the suite problem or data snapshot')
    from .problem import ProblemSpec, validate_metric_value
    from .tasks import get_adapter
    metric = report['objective']['metric']
    if provenance.get('split') != 'validation':
        raise ValueError('Fixed reference provenance must identify the validation split')
    if any(provenance.get(key) != value for key, value in report['objective'].items()):
        raise ValueError('Fixed reference provenance must match the suite objective')
    expected = get_adapter(ProblemSpec.from_dict(report['problem'])).reference_config
    if result.get('config') != expected:
        raise ValueError('Reference does not use the fixed configuration declared by the frozen problem')
    if result.get('status') != 'completed' or result.get('score') != result.get('metrics', {}).get(metric):
        raise ValueError('Reference needs a completed result with the suite objective score')
    validate_metric_value(metric, result['score'])
    artifact = Path(result.get('artifact', ''))
    if not artifact.is_absolute():
        artifact = path.parent / artifact
    if artifact.resolve().parent != path.parent or not artifact.is_file() or _digest(artifact) != result.get('artifact_hash'):
        raise ValueError('Reference artifact is missing, outside its result folder, or has a hash mismatch')
    return {key: result[key] for key in ('config', 'seed', 'score', 'metrics', 'elapsed_seconds', 'artifact_hash') if key in result} | {
        'source': {'path': path.name, 'sha256': _digest(path)}, 'provenance': provenance,
        'scope': 'Separate fixed reference fit; not a matched agent arm or evidence of a strategy advantage.'}


def build_demo(root, *, reference=None):
    """Validate the whole suite, then extract a compact, portable replay."""
    root = Path(root).resolve()
    audit = audit_suite(root)
    if not audit['passed']:
        errors = '; '.join(f"{e['scope']}: {e['code']}: {e['message']}" for e in audit['errors'])
        raise ValueError(f'Suite audit failed: {errors}')
    report = build_report_data(root)
    manifest = _read(root / 'suite.json')
    selected = next((entry for entry in manifest['schedule']
                     if entry['arm'] == 'periodic_reflection' and entry['lesson_memory'] is True), None)
    if selected is None:
        raise ValueError('Suite lacks the memory-enabled periodic_reflection demonstration arm')
    journals = {entry['run_id']: load_events(root / 'runs' / entry['run_id'] / 'events.jsonl', policy='strict')
                for entry in manifest['schedule']}
    events = journals[selected['run_id']]
    journal = f"runs/{selected['run_id']}/events.jsonl"
    chain = _chain(events, journal)
    calls = [event for records in journals.values() for event in records if event['type'] == 'model_call']
    offline = (manifest['config'].get('provider') == 'offline' or any(
        (call.get('response') or {}).get('raw', {}).get('offline') is True or
        (call.get('response') or {}).get('provider') == 'offline' for call in calls))
    metadata = manifest.get('provider_metadata') or {}
    kind = ('offline_fixture' if offline else 'recorded_provider' if metadata.get('model') == manifest['config']['model']
            and metadata.get('provider') == manifest['config']['provider'] else 'unverified_provider')
    rows = {row['run_id']: row for row in report['runs']}
    arms = [{'arm': entry['arm'], 'run_id': entry['run_id'], 'repeat': entry['repeat'],
             'best_validation_score': rows[entry['run_id']]['best_score'],
             'fits': rows[entry['run_id']]['valid_completed_trials'],
             'calls': rows[entry['run_id']]['event_counts'].get('model_call', 0),
             'known_cost': rows[entry['run_id']]['known_cost'],
             'targets': {name: {key: details.get(key) for key in ('threshold', 'reached', 'trial_id', 'seconds', 'known_cost', 'total_cost')}
                         for name, details in rows[entry['run_id']]['targets'].items()}} for entry in manifest['schedule']]
    first_memory = next(e for e in events if e['type'] == 'lesson_memory' and e['lessons'])
    timing = [{'target': name, 'first_trial_id': details['trial_id'], 'seconds': details['seconds'],
               'before_first_lesson': details['seconds'] < first_memory['elapsed_seconds']}
              for name, details in rows[selected['run_id']]['targets'].items() if details['reached']]
    sources = [root / 'suite.json'] + [root / 'runs' / entry['run_id'] / name
              for entry in manifest['schedule'] for name in ('summary.json', 'events.jsonl')]
    caveats = ['One matched repeat is a preflight observation; this replay is not evidence of a strategy advantage.'
               if manifest['repeats'] == 1 else 'This replay demonstrates recorded mechanisms; strategy claims require the full matched analysis.',
               'Planning and experiment selection run in every arm. Supervised arms share initial framing. Literature tools are disabled in this comparison.',
               'Model recommendations, hypotheses, and expected outcomes are unverified statements. Measured scores and saved configurations establish what ran.',
               'A saved lesson and its delivery establish context plumbing; they do not establish a memory benefit.']
    if kind != 'recorded_provider':
        caveats.insert(0, 'Offline or unverified provider records are not evidence of a strategy advantage.')
    return {'schema_version': 1, 'mode': 'offline_replay', 'suite': root.name,
            'evidence_kind': kind, 'strategy_evidence': False,
            'real_model_records': kind == 'recorded_provider',
            'identity': {key: report[key] for key in ('problem_hash', 'data_fingerprint', 'objective')},
            'provider': {key: metadata[key] for key in ('model', 'provider', 'source', 'timestamp') if key in metadata},
            'audit': {key: audit[key] for key in ('status', 'warnings', 'source_matches_current', 'totals')},
            'arms': arms, 'selected_arm': selected['arm'], 'selected_run': selected['run_id'],
            'selection_reason': 'Feature coverage: periodic review, explicit reflection, and lesson memory; selection is independent of winning score.',
            'chain': chain, 'first_lesson_seconds': first_memory['elapsed_seconds'], 'target_timing': timing,
            'reference': _reference(reference, report, root) if reference is not None else None,
            'sources': [{'path': str(path.relative_to(root)), 'sha256': _digest(path)} for path in sources],
            'caveats': caveats}


def _render(demo):
    chain = demo['chain']
    metric = demo['identity']['objective']['metric']
    def score(value):
        return f'{value:.6f}' if value is not None else 'unknown'
    def cite(item):
        return f"`{item['source']['path']}:{item['source']['line']}`"
    lines = ['# Workshop replay', '', f"Evidence: **{demo['evidence_kind']}**. Suite: `{demo['suite']}`.", '',
             'This is an offline replay. Generation reads records and verifies artifact hashes; it performs no model calls or training.', '',
             '## 0:00–0:45 — Set up the comparison', '',
             f"Objective: validation {metric}. {demo['selection_reason']}", '',
             '| Arm | Best validation score | Completed fits | Model calls | Recorded cost |',
             '| --- | ---: | ---: | ---: | ---: |']
    for arm in demo['arms']:
        cost = f"${arm['known_cost']:.6f}" if arm['known_cost'] is not None else 'unknown'
        lines.append(f"| {arm['arm']} | {score(arm['best_validation_score'])} | {arm['fits']} | {arm['calls']} | {cost} |")
    totals = demo['audit']['totals']
    lines += ['', f"Recorded total: {totals['runs']} runs, {totals['fits']} fits, {totals['calls']} calls, ${totals['cost']:.6f}.", '',
              'Planning occurs in every arm. Supervised arms share initial framing. Literature tools are disabled.', '',
              '## 0:45–1:30 — Read the advice and decision', '',
              f"Supervisor recommendation after trial {chain['recommendation']['after_trial']}: {chain['recommendation']['text']} ({cite(chain['recommendation'])})", '',
              f"Latest explicit reflection: {chain['reflection']['text']} ({cite(chain['reflection'])})", '',
              f"Researcher response: **{chain['decision']['supervisor_response']}**. {chain['decision']['response_reason']} ({cite(chain['decision'])})", '',
              'These are recorded model statements; their hypotheses and expectations remain unverified.', '',
              '## 1:30–2:15 — Check what actually changed and what happened', '',
              f"Baseline trial {chain['baseline']['trial_id']}: validation {metric}={score(chain['baseline']['score'])}. ({cite(chain['baseline'])})", '']
    lines += [f"- `{change['field']}`: `{json.dumps(change['before'])}` → `{json.dumps(change['after'])}`" for change in chain['changes']]
    lines += ['', f"Trial {chain['result']['trial_id']}: validation {metric}={score(chain['result']['score'])}; difference={chain['score_delta']:+.6f}. ({cite(chain['result'])})", '',
              'The difference describes these recorded fits on this split; it does not establish a general causal effect.', '',
              '## 2:15–3:00 — Follow the lesson into the next context', '',
              f"Saved lesson `{chain['lesson']['id']}`: {chain['lesson']['summary']}", '',
              f"Scope: {chain['lesson']['scope']} ({cite(chain['lesson'])})", '',
              f"The recorded researcher context before trial {chain['delivery']['before_trial_id']} contains this lesson. ({cite(chain['delivery'])})", '']
    for target in demo['target_timing']:
        if target['before_first_lesson']:
            lines += [f"Target `{target['target']}` was first reached by trial {target['first_trial_id']} at {target['seconds']:.3f}s, before the first lesson at {demo['first_lesson_seconds']:.3f}s. This crossing cannot be attributed to lesson memory.", '']
    if demo['reference']:
        reference = demo['reference']
        lines += ['## Separate fixed reference', '', f"Validation {metric}={score(reference['score'])}; configuration `{json.dumps(reference['config'], sort_keys=True)}`.", '', reference['scope'], '']
    lines += ['## Limits and fallback', '', *[f'- {item}' for item in demo['caveats']], '']
    lines += [f"- Audit warning `{warning['code']}` ({warning['scope']}): {warning['message']}" for warning in demo['audit']['warnings']]
    lines += ['', 'If live services or compute are unavailable, present this replay and the suite’s saved `report.html`. The replay JSON contains relative journal locations, line numbers, input hashes, and model artifact hashes. Keep the original suite for independent verification.', '']
    return '\n'.join(lines)


def generate_demo(root, output, *, reference=None):
    """Publish a replay separately, preserving every input artifact."""
    root, output = Path(root).resolve(), Path(output).resolve()
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Replay output must be outside the source suite and its parents')
    if reference is not None and Path(reference).resolve().is_relative_to(output):
        raise ValueError('Replay output must be outside the reference evidence')
    demo = build_demo(root, reference=reference)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'demo.json').write_text(json.dumps(demo, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    (output / 'demo.md').write_text(_render(demo), encoding='utf-8')
    return output / 'demo.md'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', type=Path, required=True, help='Existing frozen five-arm suite root')
    parser.add_argument('--output', type=Path, required=True, help='Separate directory for demo.md and demo.json')
    parser.add_argument('--reference', type=Path, help='Optional completed fixed-reference result.json')
    args = parser.parse_args(argv)
    try:
        path = generate_demo(args.suite, args.output, reference=args.reference)
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f'Replay failed: {error}\n')
    print(f'Offline replay: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
