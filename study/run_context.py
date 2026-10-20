"""Measured run state for agents; estimates are advisory, never stopping rules."""
from copy import deepcopy
import math
from statistics import mean


def target_status(targets, objective, best, selections):
    score = (best or {}).get('score', (best or {}).get('validation_auc'))
    known = type(score) in (int, float) and math.isfinite(score)
    minimize = objective['direction'] == 'minimize'
    result = []
    for target in targets:
        name, threshold = target['name'], target['value']
        crossing = selections.get(name) or {}
        reached = known and (score <= threshold if minimize else score >= threshold)
        gap = max(0., score - threshold if minimize else threshold - score) if known else None
        sentence = f"The {name} target ({threshold:g}) " + (
            'has been reached.' if reached else 'has not been reached.' if known else
            'has no completed measurement yet.')
        result.append(dict(name=name, threshold=threshold, reached=bool(reached), remaining_gap=gap,
                           first_trial_id=crossing.get('trial_id'),
                           first_elapsed_seconds=crossing.get('elapsed_seconds'), sentence=sentence))
    return result


def capacity_estimate(config, *, attempted, remaining, history, call_durations, role, framing=False, phase_completed=False):
    """Simulate scheduled calls between fits using observed means, including queue time.

    No prediction before both API and local durations exist. Retries, extra
    literature calls and changing workload may exceed the estimate.
    """
    fits = [r['duration_seconds'] for r in history if r.get('duration_seconds', 0) > 0]
    calls = [v for values in call_durations.values() for v in values if v > 0]
    cap = max(0, config.trial_cap - attempted)
    result = {'remaining_trial_cap': cap, 'estimated_additional_trials': None,
              'estimated_seconds': None, 'basis': 'observed_means',
              'sentence': 'A time estimate is unavailable until API and local trial durations are observed.'}
    if not fits or not calls:
        return result
    average, fit_mean = mean(calls), mean(fits)
    durations = {r: mean(call_durations[r]) if call_durations.get(r) else average
                 for r in ('researcher', 'supervisor', 'reflection')}
    pending = durations[role] if role != 'researcher' and not phase_completed else 0
    if role == 'supervisor' and not framing and config.reflection:
        pending += durations['reflection']
    total, count, accepted_seconds = pending, 0, 0.
    for offset in range(1, cap + 1):
        total += durations['researcher'] + fit_mean
        if total > max(0, remaining):
            break
        count, accepted_seconds = offset, total
        if config.review_every and (attempted + offset) % config.review_every == 0:
            total += durations['supervisor']
        if config.reflection:
            total += durations['reflection']
    result.update(estimated_additional_trials=count, estimated_seconds=accepted_seconds,
                  mean_trial_seconds=fit_mean, mean_call_seconds_by_role=durations,
                  sentence=f'The time estimate allows {count} additional trials (cap {cap}), including API calls, scheduled reviews, reflections and observed local wait time. Extra tool calls, retries and changing durations may reduce this estimate.')
    return result


def compact_result(result):
    """Preserve scientific observations and failures, omit duplicated runtime objects."""
    omitted = {'artifact', 'artifact_hash', 'fingerprint', 'provenance',
               'effective_config', 'actual_effective_config', 'accounting', 'experiment_diagnostic'}
    compact = deepcopy({k: v for k, v in result.items() if k not in omitted})
    diagnostics = compact.get('fit_diagnostics', {})
    losses = diagnostics.pop('training_loss', None)
    if losses:
        diagnostics['initial_training_loss'] = losses[0]
        diagnostics['final_training_loss'] = losses[-1]
    # RF aliases and defaults matter scientifically; retain resolved differences,
    # excluding execution settings already recorded by fit diagnostics/allocated_cores.
    actual = result.get('actual_effective_config', {}).get('params', {})
    requested = result.get('config', {}).get('params', {})
    derived = {k: v for k, v in actual.items() if (k not in requested or v != requested[k])
               and k not in ('device', 'n_jobs', 'random_state', 'architecture')}
    if derived:
        compact['resolved_parameters'] = derived
    return compact


def compact_feedback(contract):
    if not contract:
        return contract
    # Lessons have their own bounded ledger; don't resend their interpretations
    # inside feedback and again inside the ledger.
    return {k: deepcopy(v) for k, v in contract.items() if k != 'lesson_updates'}


def compact_lessons(lessons):
    return [{k: deepcopy(v) for k, v in lesson.items() if k != 'interpretation'} for lesson in lessons]
