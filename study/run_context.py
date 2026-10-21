"""Measured run state, advisory capacity estimates and deadline admission budgets."""
from copy import deepcopy
import math
import json
from statistics import mean


def required_start_seconds(config, *, role, history, call_durations, framing=False,
                           model=None):
    """Reserve an observed work chain before admitting another call or fit.

    A review/reflection must leave time for a researcher decision and local fit.
    Use recent maximum durations plus 25% slack, including local queue time.
    Unknown phases use other observed calls; an unseen model uses observed fits.
    Cold starts retain the configured floor. This cannot guarantee completion;
    hard timeouts remain authoritative for slow or previously unseen work.
    """
    calls = [v for values in call_durations.values() for v in values[-6:] if v > 0]
    fallback = max(calls, default=0.)
    durations = {r: max(call_durations.get(r, [])[-6:], default=fallback)
                 for r in ('researcher', 'supervisor', 'reflection')}
    completed = [r for r in history[-config.history_trials:]
                 if r.get('status') == 'completed' and r.get('duration_seconds', 0) > 0]
    matching = [r for r in completed if r.get('config', {}).get('model') == model]
    fit_seconds = max((r['duration_seconds'] for r in matching or completed), default=0.)
    if role == 'trial':
        return fit_seconds * 1.25
    required = durations['researcher'] + fit_seconds
    if role == 'supervisor':
        required += durations['supervisor']
        if config.reflection and not framing:
            required += durations['reflection']
    elif role == 'reflection':
        required += durations['reflection']
    return max(config.model_start_buffer_seconds, required * 1.25)


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
    actual = {**(result.get('effective_config') or {}).get('params', {}),
              **(result.get('actual_effective_config') or {}).get('params', {})}
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


def agent_project(project):
    """Describe generated feature indexes exactly without repeating a large name list."""
    project = {k: v for k, v in project.items() if k != 'analysis_schema'}
    names = project.get('feature_names', [])
    if len(names) > 32 and names == [f'feature_{index:04d}' for index in range(len(names))]:
        return {**{key: value for key, value in project.items() if key != 'feature_names'},
                'feature_layout': {'count': len(names), 'naming': 'feature_{index:04d}',
                                   'index_range': [0, len(names) - 1]}}
    return dict(project)


def completed_configurations(history, *, problem, project):
    """Compact execution bookkeeping for every completed effective configuration.

    Share one parameter base per model, then encode only differences. Bases are
    recorded constructor settings, including resolved defaults, rather than a
    proposed next experiment. The diagnostic gate remains the reuse authority.
    """
    from .diagnostics import describe_experiment

    bases, groups, unresolved = {}, {}, []
    execution_parameters = {'device', 'n_jobs', 'random_state', 'architecture'}
    for row in history:
        if row.get('status') != 'completed':
            continue
        config = row.get('config') or {}
        provenance = row.get('provenance') or {}
        seed = row.get('seed', provenance.get('seed'))
        effective = row.get('effective_config')
        if not effective and type(seed) is int:
            try:
                resolved = describe_experiment(config, problem=problem, project=project, seed=seed)
                effective, provenance = resolved['effective_config'], resolved['provenance']
            except (KeyError, TypeError, ValueError):
                pass
        if (type(seed) is not int or not isinstance(effective, dict)
                or not isinstance(effective.get('params'), dict)
                or not effective.get('model') or not effective.get('preprocessing')):
            # Historical incomplete evidence cannot establish equivalence. Keep
            # its existence visible without inventing defaults or a seed.
            unresolved.append({'trial_id': row['trial_id'], 'config': deepcopy(config), 'seed': seed})
            continue
        model = effective['model']
        parameters = {key: deepcopy(value) for key, value in effective['params'].items()
                      if key not in execution_parameters}
        base = bases.setdefault(model, parameters)
        key = json.dumps({'effective_config': effective, 'seed': seed,
                          'provenance': provenance}, sort_keys=True, allow_nan=False)
        if key not in groups:
            groups[key] = {'model': model, 'preprocessing': effective['preprocessing'],
                'params': {name: value for name, value in parameters.items()
                           if name not in base or value != base[name]},
                'seed': seed, 'trial_ids': []}
        groups[key]['trial_ids'].append(row['trial_id'])
    return {'scope': 'execution bookkeeping, available in every arm',
            'encoding': 'Merge parameter_bases[model] with entry.params for resolved parameters; entries include completed trials only.',
            'parameter_bases': bases, 'entries': list(groups.values()),
            **({'unresolved_trials': unresolved} if unresolved else {})}


def build_context(state, *, project, permitted_experiments, memory, role=None, framing=False,
                  reuse_feedback=None):
    """Render current budgets and observations; retain all-trial citation visibility."""
    config, summary, history = state.config, state.summary, state.history
    from .diagnostics import experiment_diagnostic
    def completed_advice(contract, field):
        candidate = (contract or {}).get(field)
        if not isinstance(candidate, dict):
            return []
        return experiment_diagnostic(candidate, problem=state.problem, project=project,
            seed=config.training_seed, history=history)['equivalent_trial_ids']
    return json.dumps({
        'project': agent_project(project),
        'recent_trials': [compact_result(row) for row in history[-config.history_trials:]],
        'completed_configurations': completed_configurations(history, problem=state.problem, project=project),
        'reused_proposals': (reuse_feedback or {}).get('count', 0),
        'last_reused_proposal': (reuse_feedback or {}).get('latest'),
        **({'permitted_experiments': permitted_experiments} if role in ('supervisor', 'reflection') else {}),
        **({'supervisor_strategy': 'standard' if framing else config.supervisor_strategy,
            'supervisor_stage': 'framing' if framing else 'review'} if role == 'supervisor' else {}),
        'best': compact_result(summary['best'] or {}),
        'last_supervisor_feedback': compact_feedback(state.feedback),
        'recommendation_completed_trial_ids': completed_advice(state.feedback, 'recommendation'),
        'reflection_completed_trial_ids': completed_advice(state.reflection, 'next_comparison'),
        'training_seed': config.training_seed,
        'active_advice_source': ('none' if state.feedback is None else
                                'initial_framing' if state.feedback == state.initial_framing else 'review'),
        'initial_framing': compact_feedback(state.initial_framing),
        'evidence_metrics_by_trial': {str(row['trial_id']): sorted(
            name for name, value in (row.get('metrics') or {}).items()
            if type(value) in (int, float) and math.isfinite(value))
            for row in history if row.get('status') == 'completed'},
        'last_explicit_reflection': compact_feedback(state.reflection),
        'trials_attempted': summary['trials'], 'trial_cap': config.trial_cap,
        'remaining_trials': max(0, config.trial_cap - summary['trials']),
        'remaining_seconds': max(0, state.remaining()), 'accounting': state.accounting.snapshot(),
        'trial_timeout_seconds': config.trial_timeout_seconds,
        'compute_limits': {'max_cores': config.max_cores or 1, 'device': config.device},
        'mean_model_call_seconds': state.model_seconds / state.accounting.calls if state.accounting.calls else None,
        'review_every_trials': config.review_every, 'reflection_after_each_trial': config.reflection,
        'objective': state.problem.objective,
        'targets': {target['name']: target['value'] for target in state.problem.targets},
        'target_status': state.targets(), 'capacity_estimate': state.capacity(role, framing),
        **({'lessons': compact_lessons(memory.snapshot())} if config.lesson_memory else {}),
    }, allow_nan=False)
