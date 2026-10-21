"""Execute an admitted experiment and durably record its measured outcome."""
import asyncio

from .events import atomic_json
from .resources import BalancedTrials
from .run_context import compact_result
from .selection import select_result


class TrialExecutor:
    def __init__(self, *, state, journal, trial_runner, data_dir, run_dir):
        self.state = state
        self.journal = journal
        self.trial_runner = trial_runner
        self.data_dir = data_dir
        self.run_dir = run_dir

    async def execute(self, arguments, diagnostic, *, intent, message):
        state, journal, config = self.state, self.journal, self.state.config
        summary = state.summary
        summary['trials'] += 1
        trial_id = summary['trials']
        journal.emit('decision', trial_id=trial_id, message=message,
                     supervisor_feedback=state.feedback, explicit_reflection=state.reflection)
        journal.emit('experiment_diagnostic', trial_id=trial_id, **diagnostic)
        journal.emit('trial_started', trial_id=trial_id, config=arguments, intent=intent)
        begin = state.clock()
        trial_limit = min(state.remaining(), config.trial_timeout_seconds)
        resource_kwargs = {}
        allocation = {}
        if isinstance(self.trial_runner, BalancedTrials):
            def resource_status(**status):
                if status['allocated_cores']:
                    allocation.update(started=state.clock(), cores=status['allocated_cores'])
                journal.emit('resources', **status)
            resource_kwargs['resource_callback'] = resource_status
        try:
            result = await asyncio.wait_for(self.trial_runner(self.data_dir,
                self.run_dir / 'trials' / f'{trial_id:04d}', arguments,
                seed=config.training_seed, timeout=trial_limit, **resource_kwargs), timeout=trial_limit)
        except TimeoutError:
            result = {'status': 'timeout', 'error': 'Trial exceeded allotted time'}
        except Exception as error:
            result = {'status': 'failed', 'error': f'{type(error).__name__}: {error}'}
        duration = state.clock() - begin
        training_duration = duration
        if resource_kwargs:
            queued = allocation.get('started', state.clock()) - begin
            result.update(queue_seconds=queued, allocated_cores=allocation.get('cores', 0))
            training_duration = max(0, duration - queued)
        summary['training_seconds'] += training_duration
        for key in ('effective_config', 'fingerprint', 'provenance'):
            result.setdefault(key, diagnostic[key])
        result['experiment_diagnostic'] = {key: diagnostic[key] for key in ('equivalent_trial_ids', 'warning')}
        result.update(trial_id=trial_id, config=arguments, seed=config.training_seed,
            elapsed_seconds=state.clock() - state.started,
            duration_seconds=duration, training_seconds=training_duration)
        if state.remaining() <= 0 and result['status'] == 'completed':
            result['status'] = 'late'
        journal.emit('trial_finished', result=result)
        select_result(summary, result, state.accounting, config, state.problem)
        journal.emit('selection', best=summary['best'], milestone=summary['milestone'],
                     stretch=summary['stretch'], target_selections=summary['target_selections'])
        atomic_json(self.run_dir / 'checkpoint.json', summary)
        state.history.append(result)
        return compact_result(result)
