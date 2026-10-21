"""Reproduce the history-index decision without fitting or making API calls.

Run from the repository root:
    .venv/bin/python -m benchmarks.history_lookup --number 1000 --repeat 5

Times are medians in microseconds per operation. The candidate index lives only
in this benchmark: comparing its lookup floor with rebuilding a completed-trial
map bounds the possible saving. Both retain the entire evidence history.
"""
import argparse
import json
from statistics import median
import timeit

from study.config import StudyConfig
from study.problem import legacy_problem
from study.reasoning import evidence_errors, ground_contract, resolve_contract_evidence, validate_contract
from study.run_context import build_context
from study.run_state import RunState


def completed_records(history):
    return {row['trial_id']: row for row in history if row.get('status') == 'completed'}


def fixture(size):
    state = RunState(StudyConfig(trial_cap=1000), legacy_problem(), clock=lambda: 0.0)
    state.history.extend({'trial_id': trial_id, 'status': 'completed',
        'metrics': {'roc_auc': .8 + trial_id / 10000}, 'duration_seconds': 1.0,
        'config': {'model': 'logistic', 'preprocessing': 'standard', 'params': {'C': trial_id}}}
        for trial_id in range(1, size + 1))
    state.summary['trials'] = size
    state.call_durations['researcher'] = [1.0]
    evidence = [{'trial_id': 1, 'metric': 'roc_auc'}, {'trial_id': size, 'metric': 'roc_auc'}]
    request = {'summary': 'Compare the measured validation runs.', 'evidence': evidence,
        'hypothesis': 'Regularization may affect validation performance.', 'baseline_trial_id': 1,
        'change': 'Adjust regularization while retaining preprocessing.',
        'expected_outcome': 'Validation performance may improve.',
        'supervisor_response': 'not_applicable', 'response_reason': 'No review is available.'}
    return state, request


def measurements(size, *, number, repeat):
    state, request = fixture(size)
    history = state.history
    index = completed_records(history)
    citations = request['evidence']

    def repeated_scan():
        # A decision with grounding, repeated validation and two lesson updates
        # can rebuild this mapping six times. This intentionally favors caching.
        for _ in range(6):
            records = completed_records(history)
            for item in citations:
                records[item['trial_id']]['metrics'][item['metric']]

    def indexed_lookup():
        for _ in range(6):
            for item in citations:
                index[item['trial_id']]['metrics'][item['metric']]

    def evidence_validation():
        contract = resolve_contract_evidence(request, history)
        assert not evidence_errors(contract['evidence'], history)
        assert not validate_contract(contract, 'researcher', history)
        grounded, _ = ground_contract(contract, history)
        assert not validate_contract(grounded, 'researcher', history)

    def context_serialization():
        return build_context(state, project={}, permitted_experiments={}, memory=None, role='researcher')

    operations = {'six_scan_lookups_us': repeated_scan, 'six_indexed_lookups_us': indexed_lookup,
                  'evidence_roundtrip_us': evidence_validation, 'context_serialization_us': context_serialization}
    # Validate fixtures outside the timer as well as exercising assertions inside it.
    evidence_validation()
    assert len(json.loads(context_serialization())['evidence_metrics_by_trial']) == size
    result = {'attempts': size}
    for name, operation in operations.items():
        result[name] = round(median(timeit.repeat(operation, number=number, repeat=repeat)) * 1e6 / number, 3)
    result['maximum_lookup_saving_us'] = round(result['six_scan_lookups_us'] - result['six_indexed_lookups_us'], 3)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--number', type=int, default=1000)
    parser.add_argument('--repeat', type=int, default=5)
    args = parser.parse_args()
    if args.number < 1 or args.repeat < 1:
        parser.error('--number and --repeat must be positive')
    print(json.dumps({'number': args.number, 'repeat': args.repeat, 'measurements': [
        measurements(size, number=args.number, repeat=args.repeat) for size in (7, 16, 100, 1000)]}, indent=2))


if __name__ == '__main__':
    main()
