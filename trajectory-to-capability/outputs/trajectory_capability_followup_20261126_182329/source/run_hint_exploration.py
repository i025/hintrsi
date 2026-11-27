#!/usr/bin/env python3
"""Optional entry, copied into source/ only if the pre-saved launch condition is met."""
import argparse
import json
import logging
import os
import signal
import time
from pathlib import Path

from benchmark.deepswe.run_loop_by_hint import HintLoopOrchestrator,build_parser,_sigint_handler

ROOT=Path(__file__).resolve().parents[1]
SERVER=Path('/srv/lab-disks/disk2/users/xymo')
DATA=SERVER/'hint-baseline-run/data'
DEADLINE=1795651320.0

def api(path,value=None):
    import urllib.request
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    request=urllib.request.Request('http://127.0.0.1:8766'+path,
        data=json.dumps(value).encode() if value is not None else None,
        headers={'Content-Type':'application/json'})
    with opener.open(request,timeout=15) as response:return json.load(response)

def service():
    import teacher_progress as progress
    from review_hint_traj import generate_progress_hint
    import uvicorn
    progress.MAX_CHECKS=1
    styles={
        'Error':'Provide an Error Hint: identify a concrete issue supported by observed code or tool results. Do not prescribe an implementation or strategy. If no observed issue warrants a reminder, return needs_hint=false.',
        'Strategy':'Provide a Strategy Hint: suggest a high-level solution direction for an observed difficulty. Do not give exact edits, task-answer code or a reference-patch recipe. If no useful direction is justified, return needs_hint=false.',
        'Exploration':'Provide an Exploration Hint: propose one small discriminating experiment to compare plausible behaviors or methods using observable inputs and outputs. Do not supply its answer or exact patch. If no useful experiment is justified, return needs_hint=false.'}
    def candidate(problem,golden,trajectory,current_hint,**kwargs):
        url=kwargs['api_base']
        variant=next((key for key in styles if '_'+key+'-r1_progress_' in url),None)
        if variant is None:raise ValueError('Unrecognized optional Hint policy session')
        policy=('\n\n# Teacher-only guidance policy (not an additional task requirement)\n'
            'Treat the reference as one known implementation, not the only correct solution. A difference from it is not by itself an error. Ground feedback in observed behavior and the original task contract. '
            +styles[variant])
        return generate_progress_hint(problem+policy,golden,trajectory,current_hint,**kwargs)
    teacher=progress.TeacherProgress(ROOT/'logs/hint_progress','http://127.0.0.1:8765',candidate=candidate)
    uvicorn.run(progress.create_app(teacher),host='127.0.0.1',port=8766)

def run():
    import pyarrow.parquet as pq
    plan_path=ROOT/'config/optional_hint_plan.json';plan=json.loads(plan_path.read_text())
    core=json.loads((ROOT/'results/attempt_metrics.json').read_text())
    if len(core)!=12 or any(a['status']!='complete' or a['formal_success']=='' for a in core):
        raise RuntimeError('Complete all core paired attempts before optional work')
    if time.time()>DEADLINE-150*60:raise RuntimeError('Less than150 minutes remain; skip optional work')
    task=plan['task'];state_path=ROOT/'runs/hint_exploration_state.json'
    if state_path.exists():raise FileExistsError(state_path)
    row=next(x for x in pq.read_table(DATA/'deep_swe_tasks.parquet',columns=['instance_id','problem_statement']).to_pylist() if x['instance_id']==task)
    golden=(DATA/'tasks'/task/'solution/solution.patch').read_text()
    state={'stage':'hint_exploration','task':task,'pid':os.getpid(),'status':'running',
        'started_at':time.time(),'planned_groups':plan['variants'],'attempts':[],'fresh_common_initial_code':True,
        'common_intermediate_state_restore':False,'independent_transfer_test':False}
    def save():state_path.write_text(json.dumps(state,indent=2)+'\n')
    os.environ.update(DOCKER_HOST='unix://'+str(SERVER/'hint-codex-experiments/vm/docker.sock'),
        HINT_CODEX_RUNTIME='/opt/hint-codex-runtime/python',PYTHONDONTWRITEBYTECODE='1')
    for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):os.environ.pop(name,None)
    signal.signal(signal.SIGINT,_sigint_handler)
    plan.update(status='running',started_at=time.time());plan_path.write_text(json.dumps(plan,indent=2)+'\n');save()
    try:
        for variant in plan['variants']:
            if time.time()>DEADLINE-2400:
                state.update(status='stopped',stop_reason='Insufficient budget for another optional attempt');break
            name='capability_hint_development_'+task+'_'+variant
            os.environ['HINT_EXPERIMENT_NAME']=name
            argv=['--instance_id',task,'--run_name',name,'--output_base',str(ROOT/'runs'),
                '--python_bin',str(SERVER/'hint-baseline-run/env/bin/python'),
                '--parquet_file',str(DATA/'deep_swe_tasks.parquet'),'--tasks_dir',str(DATA/'tasks'),
                '--model_name','gpt-6.1-terra','--api_base','http://127.0.0.1:8765',
                '--container_api_base','http://172.17.0.1:8765','--api_key','codex-local',
                '--codex_session',name,'--teacher_status_url','http://127.0.0.1:8766/experiment/status','--container_cpus','8','--mem_limit','128g',
                '--task_timeout',str(plan['student_seconds']),'--max_rounds','1','--baseline_rounds','1',
                '--no_hint_run','--skip_docker_login','--monitor_interval','30']
            if variant!='NoHint':argv+=['--teacher_progress_url','http://172.17.0.1:8766/experiment/progress']
            loop=HintLoopOrchestrator(build_parser().parse_args(argv))
            loop.sub_env.update(HTTP_PROXY='http://10.0.2.2:7897',ALL_PROXY='',all_proxy='',
                NO_PROXY='localhost,127.0.0.1,172.17.0.1',no_proxy='localhost,127.0.0.1,172.17.0.1')
            loop.summary.update(group=variant,stage='hint_exploration',mode='hint_exploration',persistent_capabilities=False)
            if variant!='NoHint':
                loop.hint_gen_dir.mkdir(parents=True,exist_ok=True)
                loop._hint_path_for_round(1).write_text('')
                registration={'session':name+'-r1','task':task,'problem_statement':row['problem_statement'],
                    'golden_diff':golden,'current_hint':'','api_base':'http://127.0.0.1:8765',
                    'api_key':'codex-local','model':'gpt-6.1-terra'}
                api('/experiment/register',registration)
            attempt={'group':variant,'run_name':name,'pid':os.getpid(),'status':'running','started_at':time.time()}
            state['attempts'].append(attempt);save()
            result=loop.step_solve(1,no_hint=variant=='NoHint')
            attempt.update(finished_at=time.time(),status='complete' if result is not None else 'technical_incomplete',
                result=result,trajs_path=str(loop._trajs_path(1)),eval_path=str(loop._eval_path(1)))
            if variant!='NoHint':attempt['teacher_status']=api('/experiment/status?session='+name+'-r1')
            loop.summary.update(total_rounds=1,solved=bool(result and result['solved']))
            loop.summary['rounds'].append(dict(attempt,round=1))
            loop._finish_summary(0 if result and result['solved'] else 1 if result else 2,
                'solved' if result and result['solved'] else 'not_solved' if result else 'technical_incomplete')
            save()
            if result is None:
                state.update(status='needs_engineering_review',stop_reason='Optional solve/eval incomplete');break
        else:state['status']='complete'
    except BaseException as exc:
        state.update(status='interrupted',stop_reason=str(exc));raise
    finally:
        state['finished_at']=time.time();save();plan['status']=state['status'];plan_path.write_text(json.dumps(plan,indent=2)+'\n')
    print(json.dumps({'state':str(state_path),'status':state['status']}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=['service','run']);args=p.parse_args()
    logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s] %(message)s')
    service() if args.mode=='service' else run()
