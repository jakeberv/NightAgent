"""Offline acceptance audit for the declared five-arm interaction comparison.

Never calls a provider, loads a model pickle, or evaluates data. Historical source
changes are warnings; missing or contradictory execution evidence is a failure.
"""
import hashlib
import json
import math
from pathlib import Path
import re

from .config import APPRENTICE_CONTRASTS, StudyConfig, comparison_arms
from .events import Accounting, atomic_json
from .run_context import compact_feedback, compact_lessons


def _digest(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


class _Audit:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.errors, self.warnings, self.runs = [], [], []
        self.matched_pairs = []
        self.source_matches_current = None

    def issue(self, code, message, scope='suite', *, warning=False):
        (self.warnings if warning else self.errors).append(
            {'scope': scope, 'code': code, 'message': message})

    def check(self, condition, code, message, scope='suite'):
        if not condition:
            self.issue(code, message, scope)
        return bool(condition)

    def read(self, path, scope='suite', *, kind=dict):
        try:
            value = json.loads(path.read_text())
            if not isinstance(value, kind):
                raise ValueError(f'Expected {kind.__name__}')
            return value
        except (OSError, ValueError) as error:
            self.issue('missing_file' if not path.exists() else 'invalid_file',
                       f'{path.name}: {error}', scope)
            return None

    def read_events(self, run):
        try:
            records = [json.loads(line) for line in (run/'events.jsonl').read_text().splitlines()]
            if not records or any(not isinstance(e, dict) or not isinstance(e.get('type'), str) for e in records):
                raise ValueError('Journal is empty or contains malformed records')
            return records
        except (OSError, ValueError) as error:
            self.issue('events', f'events.jsonl: {error}', run.name)
            return []

    def audit(self):
        manifest = self.read(self.root/'suite.json')
        if manifest is None:
            return self.result()
        try:
            config = StudyConfig(**manifest['config'])
            repeats, schedule = manifest['repeats'], manifest['schedule']
            if config.comparison != 'apprentice_interactions':
                raise ValueError('Audit supports comparison=apprentice_interactions')
            if type(repeats) is not int or repeats < 1 or not isinstance(schedule, list) or len(schedule) != repeats*5:
                raise ValueError('Schedule must contain five arms for every declared repeat')
            config.for_run(config.condition, repeats-1)
            expected = [{**arm, 'repeat': repeat, 'run_id': f"r{repeat:02d}-{arm['arm']}"}
                        for repeat in range(repeats) for arm in comparison_arms(config)]
            self.check(sorted(schedule, key=lambda e: e['run_id']) == sorted(expected, key=lambda e: e['run_id']),
                       'schedule', 'Schedule must contain each declared arm exactly once per repeat')
        except (KeyError, TypeError, ValueError) as error:
            self.issue('schedule', str(error))
            return self.result()
        self.provenance(manifest)
        for entry in expected:
            run_config = config.for_run(entry['condition'], entry['repeat'],
                supervisor_strategy=entry['supervisor_strategy'], lesson_memory=entry['lesson_memory'])
            try:
                self.run(entry, run_config, manifest)
            except (KeyError, TypeError, ValueError, IndexError, AttributeError, OSError) as error:
                self.issue('malformed_run', f'Cannot audit run evidence: {error}', entry['run_id'])
        self.reports(repeats)
        completion = self.read(self.root/'completion.json') or {}
        expected_evaluation = {'validation_only': 'skipped_validation_only', 'heldout_and_report': 'completed'}.get(manifest.get('postrun_policy'))
        self.check(expected_evaluation is not None and completion.get('postrun') ==
                   {'evaluate': expected_evaluation, 'report': 'completed'},
                   'postrun', 'Completion must confirm the declared evaluation policy and completed report')
        return self.result()

    def provenance(self, manifest):
        sources = manifest.get('provenance', {}).get('source_sha256', {})
        valid = isinstance(sources, dict) and bool(sources) and all(
            isinstance(n, str) and Path(n).name == n and isinstance(d, str) and re.fullmatch(r'[0-9a-f]{64}', d)
            for n, d in sources.items())
        if not self.check(valid, 'provenance', 'Frozen source hashes must be present and well formed'):
            return
        current = {p.name: _digest(p) for p in Path(__file__).parent.glob('*.py')}
        self.source_matches_current = sources == current
        if not self.source_matches_current:
            self.issue('source_changed', 'Current checkout differs from frozen source hashes; audit describes historical evidence.', warning=True)

    def run(self, entry, config, manifest):
        name = entry['run_id']; run = self.root/'runs'/name
        summary = self.read(run/'summary.json', name)
        es = self.read_events(run)
        if summary is None or not es:
            return
        self.check(summary.get('config') == config.to_dict(), 'config', 'Summary configuration differs from declared arm/seed', name)
        self.check(self.read(run/'config.json', name) == config.to_dict(), 'config', 'Run configuration differs from declared arm/seed', name)
        self.check(es[0]['type'] == 'run_started' and es[0].get('config') == config.to_dict(), 'config', 'Journal must begin with the declared run configuration', name)
        self.check(es[-1]['type'] == 'run_stopped' and es[-1].get('summary') == summary, 'summary', 'Summary must agree with the terminal journal record', name)
        for key in ('problem_hash', 'data_fingerprint', 'problem', 'objective', 'target_definitions'):
            self.check(manifest.get(key) is not None and summary.get(key) == manifest[key], 'identity', f'{key} differs from the suite', name)
        self.check(summary.get('stop_reason') in ('deadline', 'trial_cap', 'dollar_cap') and bool(summary.get('best')),
                   'stop', 'Run must stop at an expected limit with a valid selected model', name)
        self.check(not any(e['type'] == 'failure' for e in es), 'failure', 'Journal contains a controller failure', name)
        accounting = Accounting(); calls = [e for e in es if e['type'] == 'model_call']
        for call in calls:
            accounting.add(call.get('usage'))
            self.check(call.get('status') in ('completed', 'failed', 'cancelled'),
                       'model_call_status', 'Model call has a missing or unknown status', name)
            if call.get('status') in ('failed', 'cancelled'):
                self.issue('model_call', f"Model call ended with status {call.get('status')}", name, warning=True)
        recorded = summary.get('accounting', {})
        complete = (accounting.cost_complete and accounting.token_usage_complete and
                    recorded.get('cost_complete') is True and recorded.get('token_usage_complete') is True)
        self.check(complete and len(calls) == sum(e['type'] == 'model_call_started' for e in es),
                   'accounting', 'Calls or cost/token accounting are incomplete', name)
        self.check(all(recorded.get(k) == getattr(accounting, k) for k in ('calls', 'input_tokens', 'output_tokens')) and
                   math.isclose(recorded.get('known_cost', -1), accounting.known_cost, abs_tol=1e-9),
                   'accounting', 'Summary accounting differs from raw call usage', name)
        fits = [e['result'] for e in es if e['type'] == 'trial_finished']
        n = summary.get('trials', 0)
        ids = list(range(1, n+1)) if type(n) is int and n >= 0 else []
        self.check(n >= 7 and [r.get('trial_id') for r in fits] == ids and
                   [e.get('trial_id') for e in es if e['type'] == 'trial_started'] == ids,
                   'fit', 'Need at least seven complete attempts and matching start/finish records', name)
        verified = set()
        for fit in fits:
            self.check(fit.get('seed') == config.training_seed, 'fit_seed',
                       f"Trial {fit.get('trial_id')} used a different training seed", name)
            if not self.check(fit.get('status') == 'completed', 'fit', f"Trial {fit.get('trial_id')} did not complete", name):
                continue
            self.metric(fit, manifest['objective']['metric'], name, f"Trial {fit.get('trial_id')}")
            artifact = Path(fit.get('artifact', '')).resolve()
            try:
                valid = artifact.is_relative_to(run) and _digest(artifact) == fit.get('artifact_hash')
            except OSError:
                valid = False
            if self.check(valid, 'artifact', f"Trial {fit.get('trial_id')} artifact missing, outside its run, or hash mismatch", name):
                verified.add(fit['artifact_hash'])
        selections = {'best': summary.get('best'), **summary.get('target_selections', {})}
        self.check(all(s.get('artifact_hash') in verified for s in selections.values() if s),
                   'artifact', 'A selected artifact does not match a verified completed fit', name)
        self.selections(es, config, manifest, summary, name)
        self.interactions(es, config, n, name)
        if manifest.get('postrun_policy') == 'heldout_and_report':
            evaluated = self.read(run/'test-results.json', name) or {}
            for label, selected in selections.items():
                if selected:
                    value = evaluated.get('selections', {}).get(label, {})
                    self.check(value.get('status') == 'completed' and value.get('artifact_hash') == selected.get('artifact_hash') and
                               type(value.get('score', value.get('test_auc'))) in (int, float) and
                               math.isfinite(value.get('score', value.get('test_auc'))),
                               'heldout', f'{label} lacks a completed held-out result for its selected artifact', name)
                    self.metric(value, manifest['objective']['metric'], name, f'Held-out {label}', heldout=True)
        else:
            self.check(not (run/'test-results.json').exists(), 'heldout', 'Validation-only suite contains held-out results', name)
        self.runs.append({'run_id': name, 'arm': entry['arm'], 'repeat': entry['repeat'],
                          'training_seed': config.training_seed, 'fits': len(fits), 'artifacts_verified': len(verified),
                          'calls': len(calls), 'cost': accounting.known_cost, 'stop_reason': summary.get('stop_reason')})

    def metric(self, result, metric, name, label, *, heldout=False):
        from .problem import validate_metric_value
        values = [result['score']] if 'score' in result else []
        metrics = result.get('metrics') or {}
        if metric in metrics:
            values.append(metrics[metric])
        alias = 'test_auc' if heldout else 'validation_auc'
        if metric == 'roc_auc' and alias in result:
            values.append(result[alias])
        try:
            if not values:
                raise ValueError('Missing objective score')
            for value in values:
                validate_metric_value(metric, value)
            if any(value != values[0] for value in values[1:]):
                raise ValueError('Score and metric fields disagree')
        except (KeyError, ValueError) as error:
            self.issue('metric', f'{label}: {error}', name)

    def selections(self, es, config, manifest, summary, name):
        from .controller import initial_summary, select_result
        from .problem import ProblemSpec
        problem = ProblemSpec.from_dict(manifest['problem'])
        replay = initial_summary(config, problem, manifest['data_fingerprint'])
        accounting = Accounting()
        for event in es:
            if event['type'] == 'model_call':
                accounting.add(event.get('usage'))
            elif event['type'] == 'trial_finished':
                select_result(replay, event['result'], accounting, config, problem)
        for key in ('best', 'target_selections', 'milestone', 'stretch'):
            self.check(summary.get(key) == replay[key], 'selection',
                       f'{key} disagrees with selections reconstructed from raw fits and usage', name)

    def interactions(self, es, config, n, name):
        advice = None; source = 'none'; lessons = []; contexts = 0; delivered = 0; updates = 0
        reflection = None; completed = 0; accepted = {}; invalid = {}; decision = None
        for event in es:
            kind = event['type']
            if kind.endswith('_contract'):
                self.check(type(event.get('valid')) is bool, 'events', 'Contract is missing its validity result', name)
                # A valid decision can intentionally skip a fit and have trial_id=None.
                # Match repairs within their execution phase, not that optional ID.
                phase = (kind, completed, event.get('stage'))
                if event.get('valid') is False:
                    invalid.setdefault(phase, []).append(event)
                elif event.get('valid') is True:
                    accepted[kind] = event
                    for repaired in invalid.pop(phase, []):
                        self.issue('contract_repaired', '; '.join(repaired.get('errors') or ['Invalid contract']), name, warning=True)
            if kind in ('framing', 'review', 'reflection'):
                contract_kind = 'reflection_contract' if kind == 'reflection' else 'supervisor_contract'
                contract = accepted.pop(contract_kind, {})
                self.check(contract.get('valid') is True and contract.get('contract') == event.get('contract') and
                           contract.get('after_trial') == event.get('after_trial') and
                           contract.get('stage') == ('framing' if kind == 'framing' else 'review'),
                           'contract_evidence', f'{kind} lacks its preceding accepted contract', name)
                self.check(event.get('after_trial') == completed and (kind != 'framing' or completed == 0),
                           'interaction_order', f'{kind} is out of order relative to completed fits', name)
            if kind in ('framing', 'review'):
                advice = compact_feedback(event['contract']); source = 'initial_framing' if kind == 'framing' else 'review'
            if kind == 'reflection':
                reflection = compact_feedback(event['contract'])
            if kind == 'decision':
                decision = event
            if kind == 'trial_started':
                contract = accepted.pop('decision_contract', {})
                self.check(contract.get('valid') is True and contract.get('executed') is True and
                           contract.get('trial_id') == event.get('trial_id') and contract.get('contract') == event.get('intent') and
                           decision is not None and decision.get('trial_id') == event.get('trial_id'),
                           'contract_evidence', 'Executed fit lacks its preceding accepted decision', name)
                decision = None
            if kind == 'trial_finished':
                completed = event['result']['trial_id']
            if kind == 'lesson_memory':
                lessons = compact_lessons(event['lessons']); updates += bool(lessons)
                self.check(config.lesson_memory, 'memory', 'Disabled memory arm wrote a lesson register', name)
            if kind == 'model_call_started':
                ctx = json.loads(event['messages'][1]['content']); contexts += 1
                self.check((ctx.get('lessons') == lessons if config.lesson_memory else 'lessons' not in ctx),
                           'memory', 'Context memory must match the latest register and begin empty', name)
                if event['role'] == 'researcher':
                    delivered += bool(ctx.get('lessons'))
                    self.check(ctx.get('last_supervisor_feedback') == advice and
                               ctx.get('active_advice_source') == source and bool(advice) == bool(config.review_every),
                               'active_advice', 'Researcher did not receive the latest active advice', name)
                    self.check(ctx.get('last_explicit_reflection') == reflection,
                               'reflection_delivery', 'Researcher did not receive the latest explicit reflection', name)
            if kind == 'tool_call' and event.get('name', '').startswith('literature_'):
                self.issue('literature', 'Literature is disabled in this comparison', name)
        for pending in invalid.values():
            for event in pending:
                self.issue('contract_unrepaired', '; '.join(event.get('errors') or ['Invalid contract']), name)
        self.check(sum(e['type'] == 'framing' for e in es) == int(bool(config.review_every)),
                   'contract_evidence', 'Initial framing must occur exactly once in supervised arms', name)
        self.check(contexts > 0, 'events', 'No model contexts recorded', name)
        self.check(not config.lesson_memory or (updates > 0 and delivered > 0),
                   'memory', 'Memory arm must save a lesson and deliver it to a later researcher call', name)
        for kind, interval in (('review', config.review_every), ('reflection', 1 if config.reflection else 0)):
            actual = [e.get('after_trial') for e in es if e['type'] == kind]
            expected = list(range(interval, n, interval)) if interval else []
            self.check([x for x in actual if x != n] == expected and
                       all(type(x) is int and 1 <= x <= n for x in actual) and len(actual) == len(set(actual)) and
                       (all(x % interval == 0 for x in actual) if interval else not actual),
                       kind+'_schedule', f'{kind} schedule differs from completed attempts', name)
            if n in actual and interval and n % interval == 0:
                self.issue('final_interaction', f'{kind} after the last attempt has no subsequent experiment', name, warning=True)

    def reports(self, repeats):
        from .report import build_report_data
        try:
            data = build_report_data(self.root)
            pairs = data['paired_comparisons']
            self.matched_pairs = [p['matched_pairs'] for p in pairs]
            self.check([(p['condition_a'], p['condition_b']) for p in pairs] == list(APPRENTICE_CONTRASTS) and
                       all(p['matched_pairs'] == repeats for p in pairs) and len(data['conditions']) == 5,
                       'report', 'Need five report groups and four contrasts with every matched repeat')
            self.check(self.read(self.root/'paired-comparisons.json', kind=list) == pairs,
                       'report', 'Saved paired comparisons are missing or stale')
            expected = json.loads(json.dumps({k: v['targets'] for k, v in data['conditions'].items()}))
            self.check(self.read(self.root/'strategy-efficiency.json') == expected, 'report', 'Saved efficiency report is missing or stale')
            self.check((self.root/'report.html').is_file() and (self.root/'report.html').stat().st_size > 0,
                       'report', 'HTML report is missing or empty')
        except (OSError, ValueError, TypeError, KeyError, IndexError) as error:
            self.issue('report', f'Cannot reconstruct matched report: {error}')

    def result(self):
        return {'schema_version': 1, 'root': str(self.root), 'passed': not self.errors,
                'status': 'fail' if self.errors else 'warning' if self.warnings else 'pass',
                'errors': self.errors, 'warnings': self.warnings, 'runs': self.runs,
                'matched_pairs': self.matched_pairs, 'source_matches_current': self.source_matches_current,
                'totals': {'runs': len(self.runs), **{k: sum(r[k] for r in self.runs)
                           for k in ('fits', 'artifacts_verified', 'calls', 'cost')}}}


def audit_suite(root):
    """Return pass/warning/fail evidence without modifying the suite."""
    audit = _Audit(root)
    try:
        return audit.audit()
    except (OSError, ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        audit.issue('invalid_suite', f'Malformed suite evidence: {type(error).__name__}: {error}')
        return audit.result()


def write_audit(root):
    """Save the audit's own result; leave all experiment/report artifacts untouched."""
    result = audit_suite(root)
    atomic_json(Path(root)/'audit-summary.json', result)
    print(f"Audit {result['status']}: {len(result['errors'])} errors, {len(result['warnings'])} warnings; "
          f"{Path(root)/'audit-summary.json'}")
    return result
