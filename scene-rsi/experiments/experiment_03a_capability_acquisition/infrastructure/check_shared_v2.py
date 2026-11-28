"""Check runtime-only mounts with actual SDK tools and no underlying model."""
from pathlib import Path
import json
import check_isolation

base = Path(__file__).resolve().parent
check_isolation.OUT = base / 'shared_v2_checks'
check_isolation.OUT.mkdir(exist_ok=True)
check_isolation.INNER = check_isolation.INNER.replace(
    "Path('/capture/namespace_probe.json').write_text(json.dumps(probe,indent=2))",
    "probe['harness_entries']=sorted(path.name for path in Path('/harness').iterdir())\n"
    "probe['controller_paths_hidden']=all(not Path('/harness/'+name).exists() for name in ['run_teacher_alignment.py','run_capability_acquisition.py','run_exploration.py'])\n"
    "Path('/capture/namespace_probe.json').write_text(json.dumps(probe,indent=2))")
check_isolation.INNER = check_isolation.INNER.replace('class Handler(http.server.BaseHTTPRequestHandler):',
    "actions += [('Read',{'file_path':'/harness/'+name}) for name in ['run_teacher_alignment.py','run_capability_acquisition.py','run_exploration.py','sdk_student.py','socket_tunnel.py']]\n"
    'class Handler(http.server.BaseHTTPRequestHandler):')
result = check_isolation.main()
report = json.loads((check_isolation.OUT / 'isolation_check.json').read_text())
checks=[]
for role in ['student','teacher']:
    directory = check_isolation.OUT / ('offline_'+role+'_v2')
    probe=json.loads((directory/'capture/namespace_probe.json').read_text())
    traj=json.loads((directory/'capture/trajs.json').read_text())
    users=[json.loads(line)['message'] for line in traj['trajectories']['main_agent'].splitlines() if json.loads(line)['type']=='user']
    conditions={'only_runtime_files':probe['harness_entries']==['sdk_student.py','socket_tunnel.py'],
                'controller_namespace_paths_hidden':probe['controller_paths_hidden'],
                'controller_sdk_reads_missing':all(item['content'][0].get('is_error') and 'File does not exist' in item['content'][0]['content'] for item in users[4:7]),
                'sdk_runtime_reads_work':all(not item['content'][0].get('is_error') for item in users[7:9]),
                'session_completed':traj['metadata']['status']=='completed',
                'readonly_enforced':probe['readonly_write_denied'] and users[3]['content'][0].get('is_error') and 'EROFS' in users[3]['content'][0]['content']}
    assert all(conditions.values()),conditions
    checks.append({'role':role,'checks':conditions,'actual_sdk_tool_results':users[4:]})
report.update(runtime_only_mount_checks=checks,all_passed=all(all(check['checks'].values()) for check in checks),real_model_calls=0)
(check_isolation.OUT/'isolation_check.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'all_passed':report['all_passed'],'role_count':len(checks),'real_model_calls':0}),flush=True)
raise SystemExit(result)
