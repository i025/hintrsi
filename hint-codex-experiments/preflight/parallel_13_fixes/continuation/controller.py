"""Run isolated M/I preflight stages using the B driver's container setup."""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
B = ROOT / 'preflight/exec_action_probe/transport/complete_sdk'
sys.path.insert(0, str(B))
import driver
driver.SOURCE = ROOT / "source_parallel_13"
from driver import (PYTHON, SOURCE, create_container, install_sdk_files,
                    put, proxy_config, collect_output, restrict_network)
import docker
import pyarrow.parquet as pq
import stage_materials
from get_hint_by_task import extract_hint_from_trajs
from compress_hint import (COMPRESS_SYSTEM_PROMPT, COMPRESS_USER_TEMPLATE,
                           USAGE_GUIDELINES, call_llm)


def command(container, argv, output=None):
    code, data = container.exec_run(argv, workdir='/app')
    if output:
        output.write_bytes(data)
    assert code == 0, (argv, code, data[-3000:])
    return data.decode()


def setup(client, name, session, role, phase, output, lane, teacher=False):
    row = next(row for row in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist()
               if row['instance_id'] == 'sqlfmt-create-table-ddl-formatting')
    image = client.images.get(row['image_name'])
    container = create_container(client, image, name, 'preflight_exec_complete_sdk_' + role)
    (output / 'container.json').write_text(json.dumps({'id': container.id, 'name': name,
        'created_at_unix': time.time(), 'image': image.id, 'cpu_count': 8, 'memory_gib': 128, 'lane': lane}, indent=2))
    network = restrict_network(container, lane=lane, ports=(8785,) if teacher else (8785, 8766))
    (output / 'network.json').write_text(json.dumps(network, indent=2))
    command(container, ['bash', '-c', 'set -e; rm -rf /app /root/.claude; mkdir -p /app/data'], output / 'setup.log')
    for path in (B / 'fixture').rglob('*'):
        if path.is_file():
            put(container, '/app/' + str(path.relative_to(B / 'fixture')), path.read_bytes())
    install_sdk_files(container)
    put(container, '/tmp/m_i_guest.py', (HERE / 'm_i_guest.py').read_bytes())
    put(container, '/tmp/config.yaml', proxy_config('http://172.17.0.1:8785/sessions/' + session + '/' + role + '/' + phase + '/v1'))
    command(container, ['bash', '-c', 'set -e; git init -q /app; git -C /app config user.email preexperiment@example.invalid; '
        'git -C /app config user.name "Preexperiment fixture"; git -C /app add .; '
        'git -C /app commit -qm "Initial window report fixture"'])
    base = command(container, ['git', '-C', '/app', 'rev-parse', 'HEAD']).strip()
    if teacher:
        put(container, '/tmp/golden_diff.diff', (output.parent / 'materials/golden_diff.diff').read_bytes())
        put(container, '/tmp/teacher_system.md', (output.parent / 'materials/teacher_system.md').read_bytes())
        command(container, ['bash', '-c', 'set -e; mount --bind /app /app; mount -o remount,bind,ro /app; '
            'mount --bind /tmp/golden_diff.diff /tmp/golden_diff.diff; mount -o remount,bind,ro /tmp/golden_diff.diff'])
    command(container, ['bash', '-c', 'nohup env PYTHONPATH=/tmp PYTHONUNBUFFERED=1 LITELLM_LOCAL_MODEL_COST_MAP=True '
        '/opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml --host 127.0.0.1 --port 8768 '
        '>/tmp/proxy.log 2>&1 </dev/null &'])
    code = "import time,urllib.request\nfor i in range(600):\n try:\n  urllib.request.urlopen('http://127.0.0.1:8768/health/liveliness',timeout=1).read();break\n except OSError:\n  time.sleep(1)\nelse: raise RuntimeError('Proxy startup exceeded 600 seconds')"
    command(container, [PYTHON, '-c', code], output / 'proxy_startup.log')
    return container, base


def run_stage(container, mode, base, prompt, output, extra=()):
    target = '/tmp/' + output.name
    put(container, '/tmp/stage_prompt.txt', prompt.read_bytes())
    argv = [PYTHON, '/tmp/m_i_guest.py', mode, '--base-commit', base,
            '--prompt', '/tmp/stage_prompt.txt', '--output', target] + list(extra)
    code, stdout = container.exec_run(argv, workdir='/app')
    (output / 'host_stdout.log').write_bytes(stdout)
    collect_output(container, target, output)
    proxy_log = container.exec_run(['cat', '/tmp/proxy.log']).output
    (output / 'proxy.log').write_bytes(proxy_log)
    result = json.loads((output / 'stage_result.json').read_text())
    assert code == 0 and result['passed'], result
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=['M-initial', 'compress', 'I', 'M-review', 'cleanup'], required=True)
    parser.add_argument('--attempt', default='attempt_01')
    parser.add_argument('--lane', type=int, default=5)
    parser.add_argument('--teacher-session', default='exec-preexperiment-m')
    parser.add_argument('--student-session', default='exec-preexperiment-i-r1')
    args = parser.parse_args()
    run = HERE / args.attempt
    run.mkdir(exist_ok=True)
    state_path = run / 'teacher_state.json'
    if args.mode == 'compress':
        full_hint = (run / 'M_initial/hint_output.md').read_text()
        started = time.time()
        compressed = call_llm(COMPRESS_SYSTEM_PROMPT, COMPRESS_USER_TEMPLATE.format(full_hint=full_hint),
            'http://127.0.0.1:8785/sessions/' + args.teacher_session + '/compressor/initial_compress/v1',
            'codex-local', 'gpt-6.1-terra', 'openai')
        (run / 'hint_compact.md').write_text(USAGE_GUIDELINES.rstrip() + '\n\n---\n\n' + compressed.strip() + '\n')
        (run / 'compression.json').write_text(json.dumps({'started_at_unix': started, 'finished_at_unix': time.time(),
            'source': str(SOURCE / 'benchmark/deepswe/compress_hint.py')}, indent=2))
        return 0
    client = docker.DockerClient(base_url='unix://' + str(ROOT / f'vm-lane{args.lane}/docker.sock'), timeout=7400)
    try:
        if args.mode == 'M-initial':
            output = run / 'M_initial'
            output.mkdir()
            stage_materials.initial(B / 'problem.txt', B / 'fixture', run / 'materials')
            container, base = setup(client, 'codex-fixes13-continuous-teacher', args.teacher_session, 'teacher', 'M', output, args.lane, teacher=True)
            state = {'container_id': container.id, 'base_commit': base, 'session': args.teacher_session,
                     'output': str(output), 'retained': True, 'sdk_session_id': None, 'lane': args.lane}
            state_path.write_text(json.dumps(state, indent=2))
            result = run_stage(container, 'teacher-initial', base, run / 'materials/teacher_initial.md', output)
            if not (output / 'hint_output.md').exists():
                (output / 'hint_output.md').write_text(extract_hint_from_trajs(output / 'trajs.json'))
            assert (output / 'hint_output.md').read_text().strip()
            command(container, ['bash', '-c', 'rm -rf /tmp/M_initial /tmp/hint_output.md /tmp/stage_prompt.txt; truncate -s 0 /tmp/proxy.log'])
            state['stage_artifacts_cleared_after_export'] = True
            state['sdk_session_id'] = result['sdk_session_id']
            state_path.write_text(json.dumps(state, indent=2))
        elif args.mode == 'I':
            output = run / 'I_student'
            output.mkdir()
            stage_materials.online(B / 'problem.txt', B / 'fixture', run / 'hint_compact.md',
                run / 'materials/golden_diff.diff', run / 'I_materials', args.student_session,
                'window-report-inclusive-boundary', 'http://127.0.0.1:8785/v1')
            registration = (run / 'I_materials/registration.json').read_bytes()
            request = urllib.request.Request('http://127.0.0.1:8786/experiment/register', data=registration,
                headers={'Content-Type': 'application/json'}, method='POST')
            with urllib.request.urlopen(request, timeout=10) as response:
                (output / 'registration_result.json').write_bytes(response.read())
            container, base = setup(client, 'codex-fixes13-online-student', args.student_session, 'student', 'I1', output, args.lane)
            try:
                put(container, '/tmp/hint_compact.md', (run / 'hint_compact.md').read_bytes())
                before, before_log = container.exec_run([PYTHON, '-m', 'unittest', '-v', 'test_window_report.py'], workdir='/app')
                (output / 'tests_before.log').write_bytes(before_log)
                assert before != 0
                run_stage(container, 'student-online', base, run / 'I_materials/student_problem.txt', output,
                          ['--hint', '/tmp/hint_compact.md', '--session', args.student_session])
                code, test_log = container.exec_run([PYTHON, '-m', 'unittest', '-v', 'test_window_report.py'], workdir='/app')
                (output / 'tests_after.log').write_bytes(test_log)
                (output / 'final_patch.diff').write_text(command(container, ['git', 'diff', base]))
                changed = command(container, ['git', 'diff', '--name-only', base]).splitlines()
                unchanged = all(path == 'window_report.py' for path in changed)
                (output / 'evaluation.json').write_text(json.dumps({'tests_exit_code': code,
                    'solved': code == 0 and unchanged and 'window_report.py' in changed,
                    'changed_files': changed, 'tests_and_data_unchanged': unchanged}, indent=2))
            finally:
                container.remove(force=True)
                (output / 'cleanup.json').write_text(json.dumps({'container_removed': True, 'finished_at_unix': time.time()}))
        elif args.mode == 'M-review':
            output = run / 'M_review'
            output.mkdir()
            evaluation = json.loads((run / 'I_student/evaluation.json').read_text())
            stage_materials.review(run / 'I_student/trajs.json', run / 'hint_compact.md', run / 'materials/golden_diff.diff',
                                   run / 'review_materials', evaluation['solved'])
            state = json.loads(state_path.read_text())
            container = client.containers.get(state['container_id'])
            run_stage(container, 'teacher-review', state['base_commit'], run / 'review_materials/teacher_review.md', output,
                      ['--resume-session-id', state['sdk_session_id']])
        else:
            state = json.loads(state_path.read_text())
            client.containers.get(state['container_id']).remove(force=True)
            state.update(retained=False, removed_at_unix=time.time())
            state_path.write_text(json.dumps(state, indent=2))
    finally:
        client.close()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
