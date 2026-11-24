"""Run one original SDK student task through the local proxy and host exec bridge."""
import json
import os
import subprocess
import tarfile
import time
import urllib.request
from pathlib import Path

OUT = Path('/tmp/complete_sdk_out')
OUT.mkdir()
PYTHON = '/opt/python3.12-tmp/bin/python3'
CONFIG = json.loads(Path('/tmp/probe_config.json').read_text())


def progress(text):
    with (OUT / 'progress.log').open('a') as output:
        output.write(str(time.time()) + ' ' + text + '\n')
    print(text, flush=True)


def run_checks(name):
    process = subprocess.run([PYTHON, '-m', 'unittest', '-v', 'test_window_report.py'], cwd='/app', capture_output=True, timeout=30)
    (OUT / (name + '.log')).write_bytes(process.stdout + process.stderr)
    return process.returncode


progress('Checking the initial fixture and recording its base commit')
subprocess.run(['git', 'init', '-q', '/app'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.email', 'preexperiment@example.invalid'], check=True)
subprocess.run(['git', '-C', '/app', 'config', 'user.name', 'Preexperiment fixture'], check=True)
subprocess.run(['git', '-C', '/app', 'add', '.'], check=True)
subprocess.run(['git', '-C', '/app', 'commit', '-qm', 'Initial window report fixture'], check=True)
base = subprocess.check_output(['git', '-C', '/app', 'rev-parse', 'HEAD'], text=True).strip()
before = run_checks('tests_before')
assert before != 0, 'The intentionally faulty fixture unexpectedly passed'
with urllib.request.urlopen(CONFIG['backend'] + '/health', timeout=10) as response:
    health = json.load(response)
(OUT / 'backend_health_before.json').write_text(json.dumps(health, indent=2))
proxy_log = (OUT / 'proxy.log').open('wb')
proxy = subprocess.Popen(['/opt/python3.12-tmp/bin/litellm', '--config', '/tmp/config.yaml', '--host', '127.0.0.1', '--port', '8768'], env=dict(os.environ, PYTHONPATH='/tmp', PYTHONUNBUFFERED='1', LITELLM_LOCAL_MODEL_COST_MAP='True'), stdout=proxy_log, stderr=subprocess.STDOUT)
result = {'passed': False, 'group': 'B', 'task': 'window-report-inclusive-boundary', 'formal_deep_swe_task': False, 'ofox_calls': 0, 'config': CONFIG, 'base_commit': base, 'tests_before_exit_code': before, 'sdk_auto_compact_disabled': bool(os.getenv('DISABLE_AUTO_COMPACT')), 'started_at_unix': time.time()}
try:
    started = time.monotonic()
    for waited in range(600):
        assert proxy.poll() is None, ('Proxy startup exit', proxy.returncode)
        try:
            urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness', timeout=1).read()
            break
        except OSError:
            if waited % 30 == 0:
                progress('Waiting for the actual proxy: ' + str(waited) + ' seconds')
            time.sleep(1)
    else:
        raise AssertionError('Proxy did not start within 600 seconds')
    result['proxy_startup_seconds'] = time.monotonic() - started
    if CONFIG.get('precheck'):
        progress('Proxy ready; checking SDK paths and arguments without a model')
        help_result = subprocess.run([PYTHON, '/tmp/sdk_script.py', '--help'], capture_output=True, timeout=120)
        (OUT / 'sdk_help.log').write_bytes(help_result.stdout + help_result.stderr)
        assert help_result.returncode == 0, help_result.stderr
        assert b'--problem_statement_file' in help_result.stdout and b'--base_commit' in help_result.stdout
        program = "import json,importlib.metadata,claude_agent_sdk; from pathlib import Path; from sdk_script import create_agent_options; options=create_agent_options('/app'); print(json.dumps({'sdk_version':importlib.metadata.version('claude-agent-sdk'),'model':options.model,'cli_path':str(Path(claude_agent_sdk.__file__).parent/'_bundled/claude'),'cli_exists':(Path(claude_agent_sdk.__file__).parent/'_bundled/claude').is_file(),'sdk_environment':options.env}))"
        imported = subprocess.run([PYTHON, '-c', program], env=dict(os.environ, PYTHONPATH='/tmp'), capture_output=True, timeout=120)
        (OUT / 'sdk_import.log').write_bytes(imported.stdout + imported.stderr)
        assert imported.returncode == 0, imported.stderr
        imported_info = json.loads(imported.stdout)
        assert imported_info['cli_exists']
        cli_help = subprocess.run([imported_info['cli_path'], '--help'], capture_output=True, timeout=120)
        (OUT / 'bundled_cli_help.log').write_bytes(cli_help.stdout + cli_help.stderr)
        assert cli_help.returncode == 0, cli_help.stderr
        result.update(passed=True, precheck=True, real_model_calls=0, sdk_import=imported_info)
    else:
        progress('Proxy ready; starting the original SDK B student')
        command = [PYTHON, '/tmp/sdk_script.py', '--cwd', '/app', '--base_commit', base, '--problem_statement_file', '/tmp/problem.txt', '--output_dir', str(OUT / 'student'), '--log_path', str(OUT / 'student.log')]
        (OUT / 'sdk_command.json').write_text(json.dumps(command, indent=2))
        started = time.monotonic()
        with (OUT / 'student_stdout.log').open('wb') as log:
            completed = subprocess.run(command, cwd='/app', stdout=log, stderr=subprocess.STDOUT, timeout=900)
        result['sdk_exit_code'] = completed.returncode
        result['sdk_wall_seconds'] = time.monotonic() - started
        progress('SDK ended; evaluating the resulting code without a model')
        result['tests_after_exit_code'] = run_checks('tests_after')
        (OUT / 'final_patch.diff').write_bytes(subprocess.check_output(['git', '-C', '/app', 'diff', base]))
        (OUT / 'final_status.txt').write_bytes(subprocess.check_output(['git', '-C', '/app', 'status', '--short']))
        trajectory = json.loads((OUT / 'student/trajs.json').read_text())
        metadata = trajectory['metadata']
        result['sdk_metadata'] = metadata
        result['sdk_completed'] = metadata.get('status') == 'completed' and not metadata['ResultMessage']['is_error']
        result['sdk_session_id'] = metadata['ResultMessage']['session_id']
        rows = [json.loads(line) for line in trajectory['trajectories']['main_agent'].splitlines()]
        blocks = [block for row in rows for block in row['message'].get('content', []) if isinstance(block, dict)]
        calls = [block for block in blocks if 'name' in block and 'input' in block and 'id' in block]
        returns = [block for block in blocks if 'tool_use_id' in block]
        result['tool_names'] = [block['name'] for block in calls]
        result['tool_call_count'] = len(calls)
        result['tool_result_count'] = len(returns)
        result['tool_result_ids_complete'] = {block['id'] for block in calls} == {block['tool_use_id'] for block in returns}
        result['read_edit_bash_observed'] = all(name in result['tool_names'] for name in ('Read', 'Edit', 'Bash'))
        changed = subprocess.check_output(['git', '-C', '/app', 'diff', '--name-only', base], text=True).splitlines()
        result['changed_files'] = changed
        result['implementation_changed'] = 'window_report.py' in changed
        result['data_and_tests_unchanged'] = all(name == 'window_report.py' for name in changed)
        result['passed'] = completed.returncode == 0 and result['sdk_completed'] and result['tests_after_exit_code'] == 0 and result['tool_result_ids_complete'] and result['implementation_changed'] and result['data_and_tests_unchanged']
        with tarfile.open(OUT / 'final_workspace.tar', 'w') as archive:
            for name in ('window_report.py', 'test_window_report.py', 'README.md', 'data'):
                archive.add(Path('/app') / name, arcname=name)
finally:
    projects = Path('/root/.claude/projects')
    if projects.exists():
        with tarfile.open(OUT / 'sdk_sessions.tar', 'w') as archive:
            archive.add(projects, arcname='projects')
    result['proxy_exit_before_cleanup'] = proxy.poll()
    proxy.terminate()
    proxy.wait(timeout=15)
    proxy_log.close()
    result['finished_at_unix'] = time.time()
    (OUT / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    progress('B preexperiment finished; passed=' + str(result['passed']))
