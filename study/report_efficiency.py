"""Descriptive resource efficiency from frozen evidence; no fitted or LLM claims.

A cohort never loses runs to gain budget support. The common interval is the
intersection of observed scored prefixes, not a target-conditioned population.
"""
from collections import Counter, defaultdict
import json
import math
from statistics import mean, stdev

from .report_analysis import comparison_identity, number, treatment_name

AXES = {'tokens': 'Model tokens', 'dollars': 'API spending (USD)',
        'experiments': 'Experiment attempts'}


def resource_trajectories(artifacts, score_for_trial, row):
    """Reconstruct serial controller accounting, censoring each axis independently.

    Only completed, valid, in-allowance models update quality. All admitted
    experiments count, including failed, late and unfinished attempts. All model
    roles and retries count. Starts without finishes never imply zero usage.
    """
    curves = {axis: {'points': [], 'end': 0., 'reason': None} for axis in AXES}
    events = artifacts.events
    if (not artifacts.events_available or not artifacts.events_valid
            or not events or events[0].get('type') != 'run_started'):
        return {a: {'points': [], 'end': None, 'reason': 'Missing or corrupt journal/start evidence'} for a in AXES}
    maximize = row['objective']['direction'] == 'maximize'
    best = None
    located_accounting_gaps = set()
    pending_call = None
    pending_trial = None
    started_trials, finished_trials = set(), set()

    def stop(axes, reason):
        for axis in axes:
            if curves[axis]['reason'] is None:
                curves[axis]['reason'] = reason

    def accounting_gap(axis, reason):
        # An unrelated trial/structure limit does not locate a billing gap.
        if curves[axis]['reason'] is None:
            located_accounting_gaps.add(axis)
        stop((axis,), reason)

    def invalidate(axis, reason):
        curves[axis] = {'points': [], 'end': None, 'reason': reason}

    for index, event in enumerate(events):
        kind = event.get('type')
        if kind == 'run_started' and index:
            for axis in AXES:
                invalidate(axis, 'Duplicate run start; journal boundary is ambiguous')
            break
        if kind == 'model_call_started':
            if pending_call is not None or pending_trial is not None:
                stop(('tokens', 'dollars'), 'Overlapping calls/trials cannot be located in serial accounting')
            pending_call = (event.get('role'), event.get('attempt'))
        elif kind == 'model_call':
            account = event.get('accounting') or {}
            if not isinstance(account, dict):
                stop(('tokens', 'dollars'), 'Malformed accounting snapshot')
                account = {}
            if pending_call != (event.get('role'), event.get('attempt')):
                stop(('tokens', 'dollars'), 'Missing or mismatched model-call start')
            pending_call = None
            usage = event.get('usage') or {}
            usage = usage if isinstance(usage, dict) else {}
            incoming, outgoing = number(usage.get('prompt_tokens')), number(usage.get('completion_tokens'))
            amounts = {'tokens': incoming + outgoing if incoming is not None and outgoing is not None else None,
                       'dollars': number(usage.get('cost'))}
            for axis, amount in amounts.items():
                flag = 'token_usage_complete' if axis == 'tokens' else 'cost_complete'
                if account.get(flag) is False:
                    accounting_gap(axis, f'Frozen accounting marks {axis} incomplete at journal event {index + 1}')
                if amount is None:
                    accounting_gap(axis, f'Unknown {axis} at journal event {index + 1}')
                elif curves[axis]['reason'] is None:
                    curves[axis]['end'] += amount
            # Frozen call snapshots provide an independent cumulative check.
            inputs, outputs = number(account.get('input_tokens')), number(account.get('output_tokens'))
            token_total = inputs + outputs if inputs is not None and outputs is not None else None
            for axis, complete, value in [('tokens', 'token_usage_complete', token_total),
                                          ('dollars', 'cost_complete', number(account.get('known_cost')))]:
                if (curves[axis]['reason'] is None and account.get(complete) is True
                        and (value is None or not math.isclose(value, curves[axis]['end'], rel_tol=1e-9, abs_tol=1e-9))):
                    invalidate(axis, 'Journal usage disagrees with frozen accounting')
        elif kind == 'trial_started':
            identity = event.get('trial_id')
            if pending_call is not None:
                stop(('tokens', 'dollars'), 'Trial occurred during an unfinished model call')
            if (type(identity) is not int or identity != len(started_trials) + 1
                    or pending_trial is not None):
                stop(AXES, 'Missing, duplicate or overlapping trial start')
                continue
            started_trials.add(identity)
            pending_trial = identity
            if curves['experiments']['reason'] is None:
                curves['experiments']['end'] += 1
        elif kind == 'trial_finished':
            identity = event['result']['trial_id']
            if identity != pending_trial or identity in finished_trials:
                # Missing a trial can hide both a result and intervening spending.
                stop(AXES, 'Missing, duplicate or mismatched trial evidence')
            finished_trials.add(identity)
            pending_trial = None
            score = score_for_trial(event['result'])
            if score is not None and (best is None or (score > best if maximize else score < best)):
                best = score
            if best is not None:
                for axis, curve in curves.items():
                    if curve['reason'] is None:
                        point = {'budget': curve['end'], 'quality': best,
                                 'trial_id': identity, 'event_index': index + 1}
                        if curve['points'] and curve['points'][-1]['budget'] == point['budget']:
                            curve['points'][-1] = point
                        else:
                            curve['points'].append(point)
    if pending_call is not None:
        for axis in ('tokens', 'dollars'):
            accounting_gap(axis, 'An unfinished model call ends the known spending prefix')
    if pending_trial is not None:
        stop(('experiments',), 'An unfinished experiment is counted; its outcome is unknown')
    for axis, flag in [('tokens', 'token_usage_complete'), ('dollars', 'cost_complete')]:
        if (artifacts.summary.get('accounting') or {}).get(flag) is False and axis not in located_accounting_gaps:
            invalidate(axis, 'Frozen summary marks spending incomplete; gap cannot be located')
    for axis, field in [('tokens', 'total_tokens'), ('dollars', 'total_cost'), ('experiments', 'trial_attempts')]:
        value = number(row.get(field))
        curve = curves[axis]
        if (curve['reason'] is None and value is not None
                and not math.isclose(value, curve['end'], rel_tol=1e-9, abs_tol=1e-9)):
            invalidate(axis, 'Journal totals disagree with frozen summary')
    return curves


def quality_at(curve, budget):
    """Right-continuous incumbent; never extend beyond the observed prefix."""
    if curve['end'] is None or budget > curve['end']:
        return None
    return next((p['quality'] for p in reversed(curve['points']) if p['budget'] <= budget), None)


def improvement_area(curve, start, end, direction, discrete=False):
    """Exact step integral (or sum after attempts start+1..end), in metric units."""
    baseline = quality_at(curve, start)
    if baseline is None or end <= start or quality_at(curve, end) is None:
        return None
    sign = 1 if direction == 'maximize' else -1
    if discrete:
        return sum(sign * (quality_at(curve, k) - baseline) for k in range(int(start) + 1, int(end) + 1))
    knots = sorted({start, end, *(p['budget'] for p in curve['points'] if start < p['budget'] < end)})
    return sum((right - left) * sign * (quality_at(curve, left) - baseline)
               for left, right in zip(knots, knots[1:]))


def compare_axis(rows, axis):
    curves = [r['resource_trajectories'][axis] for r in rows]
    unavailable = [r['run_id'] for r, c in zip(rows, curves) if c['end'] is None or not c['points']]
    result = {'status': 'missing_evidence' if unavailable else 'available',
              'run_ids': [r['run_id'] for r in rows], 'unavailable_runs': unavailable,
              'start': None, 'budget': None, 'groups': {}, 'per_run': []}
    if unavailable:
        return result
    start = max(c['points'][0]['budget'] for c in curves)
    end = min(c['end'] for c in curves)
    result.update(start=start, budget=end)
    if end <= start:
        result['status'] = 'no_shared_interval'
        return result
    sign = 1 if rows[0]['objective']['direction'] == 'maximize' else -1
    for row, curve in zip(rows, curves):
        baseline, quality = quality_at(curve, start), quality_at(curve, end)
        area = improvement_area(curve, start, end, row['objective']['direction'], axis == 'experiments')
        result['per_run'].append({'run_id': row['run_id'], 'group': treatment_name(row),
            'baseline': baseline, 'quality': quality, 'improvement': sign * (quality - baseline),
            'improvement_area': area, 'mean_improvement_auc': area / (end - start)})
    knots = sorted({start, end, *(p['budget'] for c in curves for p in c['points'] if start < p['budget'] < end)})
    for group in sorted({treatment_name(r) for r in rows}):
        selected = [p for p in result['per_run'] if p['group'] == group]
        group_curves = [c for r, c in zip(rows, curves) if treatment_name(r) == group]
        result['groups'][group] = {'n': len(selected), 'total_runs': len(selected),
            **{f: mean(p[f] for p in selected) for f in ('baseline', 'quality', 'improvement', 'mean_improvement_auc')},
            'quality_sd': stdev(p['quality'] for p in selected) if len(selected) > 1 else None,
            'auc_sd': stdev(p['mean_improvement_auc'] for p in selected) if len(selected) > 1 else None,
            'curve': [{'budget': x, 'quality': mean(quality_at(c, x) for c in group_curves),
                       'improvement': mean(sign * (quality_at(c, x) - quality_at(c, start)) for c in group_curves)}
                      for x in knots]}
    return result


def summarize_efficiency(result, runs, objective):
    """Small deterministic rules over computed facts; no strategy-specific prose."""
    metric, direction = objective['metric'], objective['direction']
    problem = (runs[0].get('problem') or {}) if runs else {}
    task = problem.get('id') or problem.get('task')
    task_note = f"Task: {task}. " if task else "Task name not recorded. "
    valid = sum(r['best_score'] is not None for r in runs)
    identified = len(runs) - len(result['excluded_runs'])
    text = [task_note + f"Report covers {len(runs)} scheduled runs using validation {metric} ({direction}); "
            f"{valid}/{len(runs)} produced an observed valid model. Resource comparisons use {identified} identified runs "
            f"in {len(result['cohorts'])} frozen configuration cohort(s). "
            "Token, API spending and experiment efficiency are separate comparisons."]
    for cohort in result['cohorts']:
        membership = '; '.join(f"{g}: {len(ids)} runs" for g, ids in cohort['groups'].items())
        text.append(f"Cohort {cohort['id']} — {membership}. " +
                    ('Repeat/seed sets match across strategies.' if cohort['matched_units'] else
                     'Repeat/seed sets are unmatched or duplicated; group differences may reflect composition.'))
        for axis, facts in cohort['axes'].items():
            label = AXES[axis]
            if facts['status'] != 'available':
                reason = ('missing scored budget evidence for ' + ', '.join(facts['unavailable_runs'])
                          if facts['unavailable_runs'] else 'no positive shared observed interval')
                text.append(f"{label}: comparison unavailable ({reason}); no runs were removed to extend support.")
                continue
            groups = facts['groups']
            best = (max if direction == 'maximize' else min)(g['quality'] for g in groups.values())
            names = ', '.join(g for g, v in groups.items() if math.isclose(v['quality'], best, rel_tol=1e-12, abs_tol=1e-12))
            auc = max(g['mean_improvement_auc'] for g in groups.values())
            leaders = ', '.join(g for g, v in groups.items() if math.isclose(v['mean_improvement_auc'], auc, rel_tol=1e-12, abs_tol=1e-12))
            text.append(f"{label}: at the shared budget {facts['budget']:.6g}, the best observed group mean "
                        f"{metric} is {best:.6g} ({names}). Over {facts['start']:.6g}–{facts['budget']:.6g}, "
                        f"the largest average improvement is {auc:.6g} metric units ({leaders}; normalized AUC), "
                        "relative to each run's quality at the interval start.")
    if result['excluded_runs']:
        text.append(f"{len(result['excluded_runs'])} run(s) lack a consistent frozen comparison identity and remain listed in supporting evidence.")
    incomplete = sum(any(c['reason'] for c in r['resource_trajectories'].values()) for r in runs)
    if incomplete:
        text.append(f"{incomplete}/{len(runs)} runs have limited resource evidence; each axis stops at its known prefix, "
                    "and a missing scored prefix blocks that cohort's comparison.")
    text.append('These are descriptive differences, not evidence of strategy superiority. Budgets are chosen from observed support, '
                'not preregistered. Improvement AUC measures progress after the common start; a stronger starting model can have less subsequent gain. '
                'Fewer total trials do not show fewer trials were required for a result.')
    return text


def research_efficiency(runs, objective):
    grouped, excluded = defaultdict(list), []
    for row in runs:
        identity = comparison_identity(row)
        if identity is None:
            excluded.append({'run_id': row['run_id'], 'reason': 'Unknown or inconsistent frozen identity, configuration, repeat or seed'})
        else:
            grouped[json.dumps(identity, sort_keys=True)].append(row)
    cohorts = []
    for index, (key, rows) in enumerate(sorted(grouped.items()), 1):
        groups = {g: [r['run_id'] for r in rows if treatment_name(r) == g]
                  for g in sorted({treatment_name(r) for r in rows})}
        units = {g: Counter((r['repeat'], r['config']['training_seed']) for r in rows if treatment_name(r) == g)
                 for g in groups}
        matched = (len(groups) > 1 and all(u == next(iter(units.values())) for u in units.values())
                   and all(n == 1 for u in units.values() for n in u.values()))
        cohorts.append({'id': index, 'identity': json.loads(key), 'groups': groups,
                        'matched_units': matched, 'units': {r['run_id']: {'repeat': r['repeat'],
                            'training_seed': r['config']['training_seed'], 'stop_reason': r['stop_reason']} for r in rows},
                        'axes': {a: compare_axis(rows, a) for a in AXES}})
    result = {'schema_version': 1, 'cohorts': cohorts, 'excluded_runs': excluded,
              'method': {'baseline': 'Each run\'s observed incumbent at the common interval start; no zero-budget baseline assumed.',
                         'support': 'Start = latest first scored budget; end = earliest known prefix end across every cohort run.',
                         'normalization': 'Signed improvement in native metric units; area divided by end minus start. No score-range or percentage normalization.',
                         'continuous_area': 'Exact right-continuous step integral for tokens and dollars.',
                         'discrete_area': 'Sum after attempts start+1 through end, divided by end minus start.',
                         'accounting': 'All recorded model roles, retries and failed calls; input plus output tokens without adding cached/reasoning subsets. API charges exclude local and post-run compute.',
                         'population': 'All scheduled runs with consistent frozen identity within each configuration stratum; no success-only filtering or budget-based subgroup selection.'}}
    result['summary'] = summarize_efficiency(result, runs, objective)
    return result
