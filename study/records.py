"""Versioned journal envelopes and explicit corruption policies.

This module checks representation, not scientific validity. Selection, metric
bounds, accounting, and interaction coverage belong to their respective consumers.
The event version also defines the shape of its embedded trial result.
"""
import json
import math
from pathlib import Path
import re
from typing import Literal, NotRequired, TypedDict
from warnings import warn


EVENT_SCHEMA_VERSION = 1
CALL_STATUSES = {'completed', 'failed', 'cancelled'}
TRIAL_STATUSES = {'completed', 'failed', 'timeout', 'late'}


class TrialResult(TypedDict):
    trial_id: int
    status: Literal['completed', 'failed', 'timeout', 'late']
    config: NotRequired[dict]
    seed: NotRequired[int]
    metrics: NotRequired[dict[str, float]]
    score: NotRequired[float]
    validation_auc: NotRequired[float]
    artifact: NotRequired[str]
    artifact_hash: NotRequired[str]
    elapsed_seconds: NotRequired[float]
    duration_seconds: NotRequired[float]
    training_seconds: NotRequired[float]
    error: NotRequired[str]


class EventRecord(TypedDict):
    type: str
    schema_version: NotRequired[int]
    run_id: NotRequired[str]
    timestamp: NotRequired[str]
    elapsed_seconds: NotRequired[float]
    result: NotRequired[TrialResult | dict]


def validate_event_record(record) -> EventRecord:
    """Reject invalid envelopes and current payloads; never fill in evidence."""
    if not isinstance(record, dict) or not isinstance(record.get('type'), str) or not record['type'].strip():
        raise ValueError('Event must be an object with a nonempty type')
    if 'schema_version' in record and (type(record['schema_version']) is not int or
                                      record['schema_version'] != EVENT_SCHEMA_VERSION):
        raise ValueError(f"Unsupported schema_version: {record['schema_version']!r}")
    kind = record['type']
    if kind == 'trial_finished':
        result = record.get('result')
        if not isinstance(result, dict) or type(result.get('trial_id')) is not int or result['trial_id'] < 1:
            raise ValueError('trial_finished.result requires a positive integer trial_id')
        if not isinstance(result.get('status'), str) or result['status'] not in TRIAL_STATUSES:
            raise ValueError('trial_finished.result has an unknown status')
        for field in ('metrics', 'config'):
            if field in result and not isinstance(result[field], dict):
                raise ValueError(f'trial_finished.result.{field} must be an object')
    elif kind == 'model_call' and (not isinstance(record.get('status'), str) or record['status'] not in CALL_STATUSES):
        raise ValueError('model_call has a missing or unknown status')
    elif kind.endswith('_contract') and type(record.get('valid')) is not bool:
        raise ValueError('Contract requires a boolean valid field')
    return record


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError('JSON numbers must be finite')
    return number


def _nonfinite(value):
    raise ValueError(f'JSON numbers must be finite: {value}')


def _unfinished_json(error, line):
    """Conservatively recognize truncated tokens, never closed/interior errors."""
    if not isinstance(error, json.JSONDecodeError):
        return False
    text = line.rstrip()
    if error.msg.startswith('Unterminated string'):
        return True
    if error.msg == 'Extra data':
        return False
    if error.pos >= len(text):
        return True
    suffix = text[error.pos:]
    if error.msg == 'Expecting value':
        return suffix == '-' or any(token.startswith(suffix) for token in ('true', 'false', 'null'))
    if error.msg == "Expecting ',' delimiter":
        return bool(re.fullmatch(r'\.|[eE][+-]?', suffix))
    if error.msg.startswith('Invalid \\uXXXX escape'):
        return bool(re.fullmatch(r'u[0-9a-fA-F]{0,3}', suffix))
    return False


def load_events(path, *, policy='strict', warnings=None) -> list[EventRecord]:
    """Read a journal under strict, recover, or report policy.

    Strict rejects every invalid record. Recovery can ignore a syntactically
    unfinished final append without a newline. Reporting skips invalid records
    with a warning for each; it never fabricates a replacement result.
    """
    if policy not in ('strict', 'recover', 'report'):
        raise ValueError(f'Unknown journal read policy: {policy!r}')
    path = Path(path)
    lines = path.read_text(encoding='utf-8').splitlines(keepends=True)
    events = []
    for index, line in enumerate(lines):
        try:
            event = json.loads(line, parse_float=_finite_float, parse_constant=_nonfinite)
            events.append(validate_event_record(event))
        except (ValueError, TypeError) as error:
            incomplete = (index == len(lines)-1 and not line.endswith(('\n', '\r')) and
                          _unfinished_json(error, line))
            if policy == 'recover' and incomplete:
                continue
            message = f'Corrupt journal record in {path.name} at line {index+1}: {error}'
            if policy != 'report':
                raise ValueError(message) from error
            if warnings is None:
                warn(message, RuntimeWarning, stacklevel=2)
            else:
                warnings.append(message)
    return events
