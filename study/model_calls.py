"""Deadline admission, retries and accounting at the model API boundary."""
import asyncio

from .provider import OpenRouter
from .run_context import required_start_seconds
from .run_state import StopRun


class ModelCalls:
    def __init__(self, *, state, journal, model, context):
        self.state = state
        self.journal = journal
        self.model = model
        self.context = context

    async def __call__(self, role, messages, tools, *, framing=False):
        state, journal, config = self.state, self.journal, self.state.config
        for attempt in range(config.model_retries + 1):
            state.check()
            available = state.remaining()
            required = required_start_seconds(config, role=role, history=state.history,
                call_durations=state.call_durations, framing=framing)
            if available < required:
                journal.emit('model_call_skipped', role=role, reason='deadline_admission',
                    remaining_seconds=max(0, available), required_seconds=required,
                    model_start_buffer_seconds=config.model_start_buffer_seconds)
                raise StopRun('deadline', details={'reason': 'deadline_admission',
                    'role': role, 'remaining_seconds': max(0, available),
                    'required_seconds': required})
            # Repairs and tool turns see current budgets without duplicated history.
            messages[1] = {'role': 'user', 'content': self.context(role, framing=framing)}
            begin = state.clock()
            journal.emit('model_call_started', role=role, attempt=attempt, messages=messages, tools=tools)
            try:
                limit = min(state.remaining(), config.model_timeout_seconds)
                operation = self.model.complete(messages, tools, timeout=limit)
                # Only this reviewed implementation owns its total deadline. An
                # arbitrary adapter (including an overriding subclass) stays bounded.
                if getattr(self.model.complete, '__func__', None) is OpenRouter.complete:
                    response = await operation
                else:
                    response = await asyncio.wait_for(operation, timeout=limit)
            except asyncio.CancelledError as error:
                state.model_seconds += state.clock() - begin
                details = getattr(error, 'details', {})
                usage = details.get('usage')
                state.accounting.add(usage)
                journal.emit('model_call', role=role, attempt=attempt, status='cancelled',
                    details=details, usage=usage, accounting=state.accounting.snapshot(),
                    duration_seconds=state.clock() - begin)
                raise
            except Exception as error:
                state.model_seconds += state.clock() - begin
                details = getattr(error, 'details', {})
                usage = details.get('usage')
                state.accounting.add(usage)
                journal.emit('model_call', role=role, attempt=attempt, status='failed',
                    error=type(error).__name__, details=details, usage=usage,
                    accounting=state.accounting.snapshot(), duration_seconds=state.clock() - begin)
                # A retry is another paid attempt. Unresolved charges cannot be
                # made safe by the opt-in that permits viewing unknown-cost runs.
                if not state.accounting.cost_complete:
                    raise StopRun('unknown_cost') from error
                state.check()
                if attempt == config.model_retries:
                    raise StopRun('model_failure') from error
                continue
            duration = state.clock() - begin
            state.model_seconds += duration
            state.call_durations.setdefault(role, []).append(duration)
            state.accounting.add(response.get('usage'))
            journal.emit('model_call', role=role, attempt=attempt, status='completed',
                response=response, usage=response.get('usage'), accounting=state.accounting.snapshot(),
                duration_seconds=state.clock() - begin)
            state.check()
            return response['message']
