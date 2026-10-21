"""Journal consumers must agree on format errors without hiding lost evidence."""
import json
import time

import pytest


def journal(tmp_path, lines):
    path = tmp_path / 'events.jsonl'
    path.write_text(''.join(lines))
    return path


@pytest.mark.parametrize('record', [None, [], {}, {'type': ''}, {'type': 7},
    {'type': 'custom', 'schema_version': True}, {'type': 'custom', 'schema_version': 0},
    {'type': 'custom', 'schema_version': 2}, {'type': 'trial_finished', 'result': []},
    {'type': 'trial_finished', 'schema_version': 1},
    {'type': 'trial_finished', 'schema_version': 1, 'result': {'trial_id': 1, 'status': 'invented'}},
    {'type': 'trial_finished', 'schema_version': 1, 'result': {'trial_id': 1, 'status': []}},
    {'type': 'model_call', 'schema_version': 1, 'status': {}},
    {'type': 'model_call', 'schema_version': 1, 'status': 'invented'}])
def test_invalid_records_are_rejected_before_consumers_assume_their_shape(record):
    from study.records import validate_event_record
    with pytest.raises(ValueError):
        validate_event_record(record)


@pytest.mark.parametrize('version', [None, 1])
def test_current_result_payload_is_preserved_without_inventing_measurements(tmp_path, version):
    from study.records import load_events
    event = {'type': 'trial_finished', 'result': {'trial_id': 1, 'status': 'completed',
        'metrics': {'accuracy': .85}, 'seed': 42, 'elapsed_seconds': 3.2}}
    if version is not None:
        event['schema_version'] = version
    path = journal(tmp_path, [json.dumps(event)+'\n'])
    assert load_events(path) == [event]


@pytest.mark.parametrize('bad_line', ['{bad}\n', '[]\n', '{}\n',
    '{"type":"custom","schema_version":99}\n', '\n'])
def test_only_reporting_can_skip_a_complete_invalid_record(tmp_path, bad_line):
    from study.records import load_events
    path = journal(tmp_path, ['{"type":"first"}\n', bad_line, '{"type":"last"}\n'])
    for policy in ('strict', 'recover'):
        with pytest.raises(ValueError, match='line 2'):
            load_events(path, policy=policy)
    warnings = []
    assert load_events(path, policy='report', warnings=warnings) == [{'type':'first'}, {'type':'last'}]
    assert len(warnings) == 1 and 'events.jsonl' in warnings[0] and 'line 2' in warnings[0]


def test_only_recovery_permits_partial_final_append_without_accepting_semantic_corruption(tmp_path):
    from study.records import load_events
    path = journal(tmp_path, ['{"type":"committed"}\n', '{"type":'])
    with pytest.raises(ValueError, match='line 2'):
        load_events(path)
    assert load_events(path, policy='recover') == [{'type': 'committed'}]
    path.write_text('{"type":"committed"}\n{"type":"future","schema_version":99}')
    with pytest.raises(ValueError, match='schema_version'):
        load_events(path, policy='recover')


@pytest.mark.parametrize('tail', ['{"type":"last", BAD}', '{"type": broken}',
    '{"type":"last","value":True', '{"type":"last"} extra', '{"type":"bad\\q"}'])
def test_recovery_does_not_hide_clear_syntax_corruption_without_a_newline(tmp_path, tail):
    from study.records import load_events
    path = journal(tmp_path, ['{"type":"committed"}\n', tail])
    with pytest.raises(ValueError, match='line 2'):
        load_events(path, policy='recover')


@pytest.mark.parametrize('tail', ['{', '{"type":"last', '{"type":"last",',
    '{"type":"last","value":tru', '{"type":"last","value":-','{"type":"last","value":1.2e'])
def test_recovery_retains_committed_events_before_a_real_partial_json_prefix(tmp_path, tail):
    from study.records import load_events
    path = journal(tmp_path, ['{"type":"committed"}\n', tail])
    assert load_events(path, policy='recover') == [{'type':'committed'}]


def test_json_nonfinite_numbers_are_not_committed_evidence(tmp_path):
    from study.records import load_events
    path = journal(tmp_path, ['{"type":"trial_finished","result":{"score":NaN}}\n'])
    with pytest.raises(ValueError, match='finite'):
        load_events(path)


def test_invalid_read_policy_does_not_silently_change_corruption_handling(tmp_path):
    from study.records import load_events
    path = journal(tmp_path, ['{"type":"valid"}\n'])
    with pytest.raises(ValueError, match='policy'):
        load_events(path, policy='anything')


def test_journal_declares_event_version_and_rejects_invalid_payload_before_writing(tmp_path):
    from study.events import Journal
    writer = Journal(tmp_path, time.monotonic())
    writer.emit('custom', detail='real event')
    saved = json.loads((tmp_path/'events.jsonl').read_text())
    assert saved['schema_version'] == 1 and saved['detail'] == 'real event'
    before = (tmp_path/'events.jsonl').read_bytes()
    with pytest.raises(ValueError):
        writer.emit('trial_finished', result=[])
    assert (tmp_path/'events.jsonl').read_bytes() == before
