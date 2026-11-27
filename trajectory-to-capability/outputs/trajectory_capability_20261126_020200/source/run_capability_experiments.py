#!/usr/bin/env python3
"""Run one frozen task queue through the original no-online-teacher solve/eval steps."""
import argparse
import json
import logging
import os
import signal
import time
from pathlib import Path

from benchmark.deepswe.run_loop_by_hint import HintLoopOrchestrator, build_parser, _sigint_handler

ROOT=Path(__file__).resolve().parents[1]
OLD=Path('/srv/lab-disks/disk2/users/xymo')
DATA=OLD/'hint-baseline-run/data'

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=['selection','test'],required=True)
    parser.add_argument('--task',required=True)
    parser.add_argument('--run_tag',default='capability_v1')
    args=parser.parse_args()
    split=json.loads((ROOT/'config/task_split.json').read_text())
    if args.task not in split[args.stage]:raise ValueError('Task is outside the pre-saved split')
    preflight=json.loads((ROOT/'evidence/injection_preflight/attempt_01/capability_injection.json').read_text())
    if not preflight['content_present']:raise RuntimeError('Capability injection preflight did not pass')
    if args.stage=='test' and not (ROOT/'config/knowledge_freeze.json').exists():
        raise RuntimeError('Freeze capability libraries before Test')
    image=json.loads((ROOT/'config'/f'image_{args.task}.json').read_text())
    if not image['ready']:raise RuntimeError('Task image is unavailable')
    lane=image['lane']
    order=split['group_orders']['selection' if args.stage=='selection' else args.task]
    state_path=ROOT/'runs'/f'{args.run_tag}_{args.stage}_{args.task}_state.json'
    if state_path.exists():raise FileExistsError(state_path)
    state={'stage':args.stage,'task':args.task,'lane':lane,'pid':os.getpid(),'run_tag':args.run_tag,
        'model':'gpt-6.1-terra','reasoning_effort':'low','started_at':time.time(),
        'planned_groups':order,'attempts':[],'status':'running'}
    def save():state_path.write_text(json.dumps(state,indent=2)+'\n')
    os.environ.update(DOCKER_HOST=f'unix://{OLD}/hint-codex-experiments/vm-lane{lane}/docker.sock',
        HINT_CODEX_RUNTIME='/opt/hint-codex-runtime/python',PYTHONDONTWRITEBYTECODE='1',
        PYTHON_BIN=str(OLD/'hint-baseline-run/env/bin/python'))
    for name in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy'):os.environ.pop(name,None)
    signal.signal(signal.SIGINT,_sigint_handler)
    save()
    try:
        for group in order:
            deadline=1795651320.0
            if time.time()>deadline-2700:
                state.update(status='stopped',stop_reason='Insufficient remaining wall-clock budget for another complete attempt')
                break
            name=f'{args.run_tag}_{args.stage}_{args.task}_{group}'
            os.environ['HINT_EXPERIMENT_NAME']=name
            argv=['--instance_id',args.task,'--run_name',name,'--output_base',str(ROOT/'runs'),
                '--python_bin',str(OLD/'hint-baseline-run/env/bin/python'),
                '--parquet_file',str(DATA/'deep_swe_tasks.parquet'),'--tasks_dir',str(DATA/'tasks'),
                '--model_name','gpt-6.1-terra','--api_base','http://127.0.0.1:8765',
                '--container_api_base','http://172.17.0.1:8765','--api_key','codex-local',
                '--codex_session',name,'--container_cpus','8','--mem_limit','128g',
                '--task_timeout','1800','--max_rounds','1','--baseline_rounds','1',
                '--no_hint_run','--skip_docker_login','--monitor_interval','30']
            if group!='B0':
                capability=ROOT/'knowledge'/f'{group}_v1.md'
                if args.stage=='test':
                    freeze=json.loads((ROOT/'config/knowledge_freeze.json').read_text())
                    capability=Path(freeze['libraries'][group]['path'])
                argv += ['--capability_path',str(capability)]
            loop=HintLoopOrchestrator(build_parser().parse_args(argv))
            loop.sub_env.update(HTTP_PROXY='http://10.0.2.2:7897',ALL_PROXY='',all_proxy='',
                NO_PROXY='localhost,127.0.0.1,172.17.0.1',no_proxy='localhost,127.0.0.1,172.17.0.1')
            loop.summary.update(group=group,stage=args.stage,knowledge_version='none' if group=='B0' else 'v1',online_teacher=False)
            attempt={'group':group,'run_name':name,'started_at':time.time(),'status':'running','pid':os.getpid()}
            state['attempts'].append(attempt);save()
            code=loop.run()
            attempt.update(status='complete' if code in (0,1) else 'technical_incomplete',
                exit_code=code,finished_at=time.time(),summary=loop.summary)
            if group!='B0' and code in (0,1):
                proof_path=ROOT/'runs'/(name+'_r1')/'infer_logs'/args.task/'turn_1/capability_injection.json'
                proof=json.loads(proof_path.read_text()) if proof_path.exists() else {}
                if proof.get('content_present') is not True:
                    attempt.update(status='invalid_knowledge_condition',injection_proof=proof)
                    code=2
            save()
            if code not in (0,1):
                state.update(status='needs_engineering_review',stop_reason='Original solve/eval chain did not complete; preserve failure and inspect before continuing')
                break
        else:state['status']='complete'
    except BaseException as exc:
        state.update(status='interrupted',stop_reason=str(exc));raise
    finally:
        state['finished_at']=time.time();save()
    print(json.dumps({'state':str(state_path),'status':state['status']}),flush=True)

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO,format='%(asctime)s [%(levelname)s] %(message)s')
    main()
