"""Acceptance audit must catch plausible bad evidence without running models or evaluation."""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from study.config import StudyConfig
from study.controller import run_one
from study.fake import FakeModel
from study.report import build_report_data
from study.science import prepare_dataset
from study.suite import run_suite


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n')


def events(run):
    return [json.loads(line) for line in (run/'events.jsonl').read_text().splitlines()]


def save_events(run, records):
    (run/'events.jsonl').write_text(''.join(json.dumps(e)+'\n' for e in records))


@pytest.fixture(scope='module')
def recorded_suite(tmp_path_factory):
    root=tmp_path_factory.mktemp('audit-recording'); data=root/'data'; prepare_dataset(data, synthetic=True)
    async def fit(data_dir, trial_dir, config, *, seed, timeout):
        trial_dir.mkdir(parents=True); artifact=trial_dir/'model.joblib'
        artifact.write_bytes(f'fixture {seed} {config}'.encode())
        return {'status':'completed','metrics':{'roc_auc':.94},'validation_auc':.94,
                'artifact':str(artifact),'artifact_hash':hashlib.sha256(artifact.read_bytes()).hexdigest()}
    async def runner(config, data_dir, run_dir, model, **kwargs):
        kwargs.pop('trial_runner',None)
        return await run_one(config,data_dir,run_dir,model,trial_runner=fit,**kwargs)
    config=StudyConfig(comparison='apprentice_interactions',model='offline-script',provider='offline',
                       device='cpu',trial_cap=7,allowance_seconds=60,max_cores=4)
    asyncio.run(run_suite(config,data,root/'suite',repeats=3,
        deadline=datetime.now(timezone.utc)+timedelta(hours=1),reserve_seconds=600,
        model_factory=lambda _:FakeModel(options=[{'model':'logistic','preprocessing':'standard',
                                                   'params':{'C':i}} for i in range(1,8)]),
        runner=runner,validation_only=True))
    suite=root/'suite'
    write(suite/'completion.json',{'postrun':{'evaluate':'skipped_validation_only','report':'completed'}})
    report=build_report_data(suite)
    write(suite/'paired-comparisons.json',report['paired_comparisons'])
    write(suite/'strategy-efficiency.json',{n:v['targets'] for n,v in report['conditions'].items()})
    (suite/'report.html').write_text('<html>fixture report</html>')
    return suite


@pytest.fixture
def suite(recorded_suite,tmp_path):
    target=tmp_path/'suite';shutil.copytree(recorded_suite,target)
    for path in target.rglob('*'):
        if path.suffix in ('.json','.jsonl'):
            path.write_text(path.read_text().replace(str(recorded_suite),str(target)))
    return target


def audit(root):
    from study.audit import audit_suite
    return audit_suite(root)


def codes(result):
    return {e['code'] for e in result['errors']}


def test_complete_five_arm_repeats_pass_without_modifying_evidence(suite):
    before={str(p):p.read_bytes() for p in suite.rglob('*') if p.is_file()}
    result=audit(suite)
    assert result['passed'] and result['status']=='pass',result
    assert result['totals']['runs']==15 and result['totals']['fits']==105
    assert result['matched_pairs']==[3,3,3,3]
    assert {str(p):p.read_bytes() for p in suite.rglob('*') if p.is_file()}==before


def test_repaired_contract_is_warning_not_failed_coverage(suite):
    run=suite/'runs/r00-periodic_reflection_memory';es=events(run)
    i=next(i for i,e in enumerate(es) if e['type']=='reflection_contract' and e['valid'])
    es.insert(i,{**es[i],'valid':False,'errors':['scope exceeds maximum length']});save_events(run,es)
    result=audit(suite)
    assert result['passed'] and result['status']=='warning',result
    assert any(w['code']=='contract_repaired' for w in result['warnings'])


@pytest.mark.parametrize('mutation,expected',[
    ('missing_run','missing_file'),('artifact','artifact'),('incomplete_call','accounting'),
    ('memory_delivery','memory'),('memory_leak','memory'),('review','review_schedule'),
    ('reflection','reflection_schedule'),('advice','active_advice'),('unrepaired','contract_unrepaired'),
    ('seed','config'),('duplicate_schedule','schedule'),('stale_pairs','report'),
    ('heldout_missing','postrun'),('corrupt_events','events'),('failed_fit','fit'),
    ('missing_source','provenance'),('no_literature','literature')])
def test_incomplete_or_inconsistent_evidence_fails(suite,mutation,expected):
    run=suite/'runs/r00-periodic_reflection_memory';es=events(run)
    if mutation=='missing_run': (run/'summary.json').unlink()
    elif mutation=='artifact': Path(next(e['result']['artifact'] for e in es if e['type']=='trial_finished')).write_bytes(b'tampered')
    elif mutation=='incomplete_call':
        e=next(e for e in es if e['type']=='model_call');e['usage']=None;save_events(run,es)
    elif mutation=='memory_delivery':
        for e in es:
            if e['type']=='model_call_started' and e['role']=='researcher':
                c=json.loads(e['messages'][1]['content']);c['lessons']=[];e['messages'][1]['content']=json.dumps(c)
        save_events(run,es)
    elif mutation=='memory_leak':
        run=suite/'runs/r00-periodic';es=events(run)
        e=next(e for e in es if e['type']=='model_call_started');c=json.loads(e['messages'][1]['content']);c['lessons']=[];e['messages'][1]['content']=json.dumps(c);save_events(run,es)
    elif mutation in ('review','reflection'):
        save_events(run,[e for e in es if e['type']!=mutation or e['after_trial']!=3])
    elif mutation=='advice':
        e=next(e for e in es if e['type']=='model_call_started' and e['role']=='researcher');c=json.loads(e['messages'][1]['content']);c['last_supervisor_feedback']=None;e['messages'][1]['content']=json.dumps(c);save_events(run,es)
    elif mutation=='unrepaired':
        e=next(e for e in reversed(es) if e['type']=='reflection_contract');e['valid']=False;e['errors']=['unrepaired'];save_events(run,es)
    elif mutation=='seed':
        s=read(run/'summary.json');s['config']['training_seed']=999;write(run/'summary.json',s)
    elif mutation=='duplicate_schedule':
        s=read(suite/'suite.json');s['schedule'][1]=s['schedule'][0];write(suite/'suite.json',s)
    elif mutation=='stale_pairs': write(suite/'paired-comparisons.json',[])
    elif mutation=='heldout_missing':
        s=read(suite/'suite.json');s['postrun_policy']='heldout_and_report';write(suite/'suite.json',s)
    elif mutation=='corrupt_events': (run/'events.jsonl').write_text('{truncated')
    elif mutation=='failed_fit':
        next(e for e in es if e['type']=='trial_finished')['result']['status']='failed';save_events(run,es)
    elif mutation=='missing_source':
        s=read(suite/'suite.json');s['provenance']['source_sha256']={};write(suite/'suite.json',s)
    elif mutation=='no_literature':
        es.insert(-1,{'type':'tool_call','name':'literature_search','role':'supervisor','result':{}});save_events(run,es)
    result=audit(suite)
    assert not result['passed'] and result['status']=='fail'
    assert expected in codes(result),result


def test_old_source_snapshot_warns_without_invalidating_saved_run(suite):
    s=read(suite/'suite.json');s['provenance']['source_sha256']['controller.py']='0'*64;write(suite/'suite.json',s)
    result=audit(suite)
    assert result['passed'] and any(w['code']=='source_changed' for w in result['warnings'])


def test_heldout_policy_requires_each_selected_artifact_result(suite):
    s=read(suite/'suite.json');s['postrun_policy']='heldout_and_report';write(suite/'suite.json',s)
    write(suite/'completion.json',{'postrun':{'evaluate':'completed','report':'completed'}})
    assert 'heldout' in codes(audit(suite))
    for run in (suite/'runs').iterdir():
        s=read(run/'summary.json');selected={'best':s['best'],**s['target_selections']}
        write(run/'test-results.json',{'selections':{name:{'status':'completed','artifact_hash':x['artifact_hash'],'score':.9} for name,x in selected.items() if x}})
    assert audit(suite)['passed']
    run=suite/'runs/r00-frequent';s=read(run/'test-results.json');s['selections']['best']['artifact_hash']='wrong';write(run/'test-results.json',s)
    assert 'heldout' in codes(audit(suite))


def test_audit_cli_retains_failure_summary_and_returns_nonzero(suite):
    (suite/'runs/r00-frequent/summary.json').unlink()
    p=subprocess.run([sys.executable,'-m','study','audit','--output',str(suite)],capture_output=True,text=True)
    assert p.returncode==2,p.stdout+p.stderr
    result=read(suite/'audit-summary.json');assert not result['passed']
    assert 'missing_file' in codes(result)


def test_dedicated_overnight_configuration_uses_approved_budget():
    from study.config import comparison_arms
    path=Path('study/fashion-five-arm-overnight-config.json')
    assert path.exists(), 'Dedicated five-arm overnight configuration is missing'
    c=StudyConfig(**read(path))
    assert (c.comparison,c.allowance_seconds,c.trial_cap,c.dollar_cap)==('apprentice_interactions',600,1000,5)
    assert len(comparison_arms(c))==5 and c.for_run('periodic',2).training_seed==44
    assert c.max_cores==4 and c.device=='mps'


@pytest.mark.parametrize('postrun_fails',[False,True])
def test_suite_audit_gate_retains_verdict_even_after_postrun_failure(suite,recorded_suite,monkeypatch,postrun_fails):
    from types import SimpleNamespace
    from study import __main__ as cli
    manifest=read(suite/'suite.json');config=suite/'launch-config.json';write(config,manifest['config'])
    class OfflineModel(FakeModel):
        async def describe(self): return {'offline':True}
    monkeypatch.setattr(cli,'live_model',lambda _:OfflineModel())
    async def recorded_search(*args,**kwargs):
        return [read(p) for p in (suite/'runs').glob('*/summary.json')]
    async def postrun(*args,**kwargs):
        if postrun_fails:
            write(suite/'completion.json',{'postrun':{'evaluate':'skipped_validation_only','report':'failed'}})
            raise RuntimeError('report failed')
    monkeypatch.setattr(cli,'run_suite',recorded_search)
    monkeypatch.setattr(cli,'finish_before_deadline',postrun)
    (suite/'runs/r00-frequent/summary.json').unlink()
    args=SimpleNamespace(command='suite',config=config,data=recorded_suite.parent/'data',output=suite,
        repeats=3,deadline=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat(),reserve_seconds=1200,
        order_seed=2026,validation_only=True,audit=True,quiet=True)
    with pytest.raises(RuntimeError,match='report failed' if postrun_fails else 'Audit failed'):
        asyncio.run(cli.dispatch(args))
    assert not read(suite/'audit-summary.json')['passed']


@pytest.mark.parametrize('field,value',[('provenance',None),('postrun_policy',[]),('schedule',[None]*15)])
def test_malformed_manifest_returns_failed_audit_instead_of_crashing(suite,field,value):
    manifest=read(suite/'suite.json');manifest[field]=value;write(suite/'suite.json',manifest)
    result=audit(suite)
    assert not result['passed'] and result['errors']


def test_cli_warning_exits_successfully_and_writes_summary(suite):
    manifest=read(suite/'suite.json');manifest['provenance']['source_sha256']['controller.py']='0'*64;write(suite/'suite.json',manifest)
    result=subprocess.run([sys.executable,'-m','study','audit','--output',str(suite)],capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    assert read(suite/'audit-summary.json')['status']=='warning'


@pytest.mark.parametrize('mutation,expected',[
    ('missing_contracts','contract_evidence'),('reflection_delivery','reflection_delivery'),
    ('late_reflections','interaction_order'),('off_cadence_final_review','review_schedule'),
    ('missing_targets','selection'),('selected_path','selection'),('selected_score','selection'),
    ('fit_seed','fit_seed'),('call_status','events')])
def test_audit_rejects_contradictions_despite_consistent_summary_and_reports(suite,mutation,expected):
    run=suite/'runs/r00-periodic_reflection_memory';es=events(run);summary=read(run/'summary.json')
    if mutation=='missing_contracts': es=[e for e in es if not e['type'].endswith('_contract')]
    elif mutation=='reflection_delivery':
        for e in es:
            if e['type']=='model_call_started' and e['role']=='researcher':
                ctx=json.loads(e['messages'][1]['content']);ctx['last_explicit_reflection']=None
                e['messages'][1]['content']=json.dumps(ctx)
    elif mutation=='late_reflections':
        moved=[e for e in es if e['type']=='reflection'];es=[e for e in es if e['type']!='reflection']
        es[-1:-1]=moved
    elif mutation=='off_cadence_final_review':
        review=next(e for e in es if e['type']=='review')
        es.insert(-1,{**review,'after_trial':7})
    elif mutation=='missing_targets': summary.pop('target_selections')
    elif mutation=='selected_path': summary['best']['artifact']='/tmp/nonexistent-audit-model'
    elif mutation=='selected_score':
        summary['best'].update(score=.1,validation_auc=.1,metrics={'roc_auc':.1})
    elif mutation=='fit_seed':
        for e in es:
            if e['type']=='trial_finished': e['result']['seed']=999
    elif mutation=='call_status': next(e for e in es if e['type']=='model_call')['status']='not-a-valid-status'
    es[-1]['summary']=summary;write(run/'summary.json',summary);save_events(run,es)
    report=build_report_data(suite)
    write(suite/'paired-comparisons.json',report['paired_comparisons'])
    write(suite/'strategy-efficiency.json',{k:v['targets'] for k,v in report['conditions'].items()})
    result=audit(suite)
    assert not result['passed'] and expected in codes(result),result


@pytest.mark.parametrize('reason',['deadline_admission','equivalent'])
def test_repaired_decision_without_executed_trial_is_warning(suite,reason):
    run=suite/'runs/r00-periodic_reflection_memory';es=events(run)
    contract=next(e for e in es if e['type']=='decision_contract' and e['valid'])
    es[-1:-1]=[{**contract,'trial_id':8,'valid':False,'errors':['repair this decision']},
               {**contract,'trial_id':None,'valid':True,'executed':False,'not_executed_reason':reason}]
    save_events(run,es)
    result=audit(suite)
    assert result['passed'] and any(w['code']=='contract_repaired' for w in result['warnings']),result


@pytest.mark.parametrize('heldout,inconsistent',[(False,False),(False,True),(True,False),(True,True)])
def test_invalid_or_contradictory_metrics_fail_even_for_unselected_fits(suite,heldout,inconsistent):
    run=suite/'runs/r00-periodic_reflection_memory'
    if heldout:
        manifest=read(suite/'suite.json');manifest['postrun_policy']='heldout_and_report';write(suite/'suite.json',manifest)
        write(suite/'completion.json',{'postrun':{'evaluate':'completed','report':'completed'}})
        for path in (suite/'runs').iterdir():
            summary=read(path/'summary.json');selected={'best':summary['best'],**summary['target_selections']}
            write(path/'test-results.json',{'selections':{k:{'status':'completed','artifact_hash':v['artifact_hash'],'score':.9} for k,v in selected.items() if v}})
        result=read(run/'test-results.json');value=result['selections']['best']
    else:
        es=events(run);value=next(e['result'] for e in reversed(es) if e['type']=='trial_finished')
    value.update(score=.2 if inconsistent else 2,metrics={'roc_auc':.94 if inconsistent else 2})
    value['test_auc' if heldout else 'validation_auc']=.94 if inconsistent else 2
    if heldout: write(run/'test-results.json',result)
    else: save_events(run,es)
    result=audit(suite)
    assert not result['passed'] and 'metric' in codes(result),result


def test_audit_catches_a_selection_bug_even_when_production_selector_agrees(suite,monkeypatch):
    """Fault injection: a last-trial-wins selector must not become the audit oracle."""
    from study.events import Accounting
    from study import selection
    run=suite/'runs/r00-periodic_reflection_memory';es=events(run)
    last=next(e['result'] for e in reversed(es) if e['type']=='trial_finished')
    account=Accounting()
    for e in es:
        if e['type']=='model_call': account.add(e['usage'])
    summary=read(run/'summary.json')
    summary['best']={**summary['best'],**{k:last[k] for k in
        ('trial_id','elapsed_seconds','artifact','artifact_hash','config')},'accounting':account.snapshot()}
    es[-1]['summary']=summary;write(run/'summary.json',summary);save_events(run,es)
    original=selection.select_result
    def last_wins(summary,result,accounting,config,problem=None):
        original(summary,result,accounting,config,problem)
        if config.condition=='periodic_reflection' and config.lesson_memory and config.repeat==0:
            latest={}
            original(latest,result,accounting,config,problem)
            if latest.get('best'): summary['best']=latest['best']
    monkeypatch.setattr(selection,'select_result',last_wins)
    report=build_report_data(suite)
    write(suite/'paired-comparisons.json',report['paired_comparisons'])
    write(suite/'strategy-efficiency.json',{k:v['targets'] for k,v in report['conditions'].items()})
    result=audit(suite)
    assert any(e['code']=='selection' and e['scope']==run.name for e in result['errors']),result


@pytest.mark.parametrize('field,value', [('problem_hash', 'different-problem'),
    ('data_fingerprint', 'different-data'), ('problem', {'id': 'different-problem'})])
def test_run_start_identity_must_match_the_frozen_suite(suite, field, value):
    run = suite/'runs/r00-periodic'; es = events(run)
    es[0][field] = value
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'] and 'identity' in codes(result), result


@pytest.mark.parametrize('mutation', ['role', 'attempt', 'order'])
def test_model_calls_must_pair_in_journal_order_by_role_and_attempt(suite, mutation):
    run = suite/'runs/r00-periodic'; es = events(run)
    i = next(i for i,e in enumerate(es) if e['type'] == 'model_call')
    if mutation == 'role':
        es[i]['role'] = 'researcher'
    elif mutation == 'attempt':
        es[i]['attempt'] = 1
    else:
        completion = es.pop(i)
        start = next(i for i,e in enumerate(es) if e['type'] == 'model_call_started')
        es.insert(start, completion)
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'] and 'model_call_order' in codes(result), result


def test_worker_seed_cannot_contradict_the_controller_seed(suite):
    run = suite/'runs/r00-periodic'; es = events(run)
    fit = next(e['result'] for e in reversed(es) if e['type'] == 'trial_finished')
    fit['actual_effective_config'] = {'params': {'random_state': 999}}
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'] and 'fit_seed' in codes(result), result


def test_preloaded_memory_is_rejected_even_when_context_matches_the_register(suite):
    run = suite/'runs/r00-periodic_reflection_memory'; es = events(run)
    i = next(i for i,e in enumerate(es) if e['type'] == 'lesson_memory' and e['lessons'])
    lesson_event = es[i]
    from study.run_context import compact_lessons
    for event in es[:i]:
        if event['type'] == 'model_call_started':
            ctx = json.loads(event['messages'][1]['content'])
            ctx['lessons'] = compact_lessons(lesson_event['lessons'])
            event['messages'][1]['content'] = json.dumps(ctx)
    es.insert(1, lesson_event.copy())
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'] and 'memory' in codes(result), result


@pytest.mark.parametrize('kind,arm', [('review', 'periodic'), ('reflection', 'periodic_reflection')])
def test_due_treatment_must_precede_the_next_researcher_call(suite, kind, arm):
    run = suite/'runs'/('r00-'+arm); es = events(run)
    end = next(i for i,e in enumerate(es) if e['type'] == kind and e['after_trial'] == 3)
    role = 'supervisor' if kind == 'review' else 'reflection'
    begin = max(i for i in range(end) if es[i]['type'] == 'model_call_started' and es[i]['role'] == role)
    prior = next(e for e in reversed(es[:begin])
                 if e['type'] == 'model_call_started' and e['role'] == 'researcher')
    previous_context = json.loads(prior['messages'][1]['content'])
    phase = es[begin:end+1]; del es[begin:end+1]
    next_start = next(i for i in range(begin, len(es))
                      if es[i]['type'] == 'model_call_started' and es[i]['role'] == 'researcher')
    ctx = json.loads(es[next_start]['messages'][1]['content'])
    keys = ('last_supervisor_feedback', 'active_advice_source') if kind == 'review' else ('last_explicit_reflection',)
    for key in keys:
        ctx[key] = previous_context[key]
    es[next_start]['messages'][1]['content'] = json.dumps(ctx)
    next_end = next(i for i in range(next_start+1, len(es)) if es[i]['type'] == 'model_call')
    es[next_end+1:next_end+1] = phase
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'] and 'interaction_order' in codes(result), result


def test_relabelled_researcher_calls_cannot_certify_fits(suite):
    run = suite/'runs/r00-researcher_alone'; es = events(run)
    for event in es:
        if event['type'] in ('model_call_started', 'model_call'):
            event['role'] = 'supervisor'
    save_events(run, es)
    result = audit(suite)
    assert not result['passed'] and 'role_coverage' in codes(result), result


@pytest.mark.parametrize('heldout,status,score', [(False, 'in_progress', None),
    (True, 'failed', None), (True, 'uncertain', None), (True, 'in_progress', None),
    (True, 'completed', .1)])
def test_shared_heldout_cache_cannot_contradict_policy_or_run_views(suite, heldout, status, score):
    if heldout:
        manifest = read(suite/'suite.json'); manifest['postrun_policy'] = 'heldout_and_report'
        write(suite/'suite.json', manifest)
        write(suite/'completion.json', {'postrun': {'evaluate': 'completed', 'report': 'completed'}})
        for run in (suite/'runs').iterdir():
            summary = read(run/'summary.json')
            selected = {'best': summary['best'], **summary['target_selections']}
            write(run/'test-results.json', {'selections': {name: {
                'status': 'completed', 'artifact_hash': value['artifact_hash'], 'score': .9}
                for name,value in selected.items() if value}})
    digest = read(suite/'runs/r00-periodic/summary.json')['best']['artifact_hash']
    cache = suite/'evaluation'; cache.mkdir(exist_ok=True)
    write(cache/'test-evaluation-cache.json', {'artifacts': {digest: {
        'artifact_hash': digest, 'status': status, 'score': score}}})
    result = audit(suite)
    assert not result['passed'] and 'heldout' in codes(result), result
