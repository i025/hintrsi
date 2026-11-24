"""Run one M or I stage with the original SDK; the driver owns proxy and container lifetime."""
import argparse
import errno
import json
import os
import subprocess
import tarfile
import time
from pathlib import Path

PYTHON = '/opt/python3.12-tmp/bin/python3'


def readonly(path):
    try:
        descriptor = os.open(path, os.O_WRONLY)
    except OSError as error:
        return {'path': path, 'write_open_denied': True, 'errno': error.errno,
                'readonly_mount': error.errno == errno.EROFS}
    else:
        os.close(descriptor)
        return {'path': path, 'write_open_denied': False, 'readonly_mount': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['teacher-initial', 'teacher-review', 'student-online'])
    parser.add_argument('--base-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--system-prompt', default='/tmp/teacher_system.md')
    parser.add_argument('--resume-session-id')
    parser.add_argument('--hint')
    parser.add_argument('--session')
    parser.add_argument('--task', default='window-report-inclusive-boundary')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    teacher = args.stage.startswith('teacher')
    result = {'stage': args.stage, 'passed': False, 'started_at_unix': time.time(),
              'sdk_script': '/tmp/sdk_script.py', 'sdk_context_owner': 'Claude SDK',
              'codex_exec_resume_used': False, 'formal_experiment': False}
    env = dict(os.environ)
    if teacher:
        checks = [readonly('/app/window_report.py'), readonly('/tmp/golden_diff.diff')]
        result['readonly_checks'] = checks
        assert all(check['readonly_mount'] for check in checks), checks
        env.update(TEACHER_MODE='1', EXPERIMENT_ROLE='teacher', SYSTEM_PROMPT_FILE=args.system_prompt)
        env.pop('TEACHER_PROGRESS_URL', None)
        env.pop('APPEND_SYSTEM_PROMPT_FILE', None)
    else:
        assert args.hint and args.session
        assert not Path('/tmp/golden_diff.diff').exists(), 'The student must not receive the reference patch'
        env.update(TEACHER_MODE='0', EXPERIMENT_ROLE='student', SYSTEM_PROMPT_FILE='',
                   APPEND_SYSTEM_PROMPT_FILE=args.hint, EXPERIMENT_SESSION=args.session,
                   EXPERIMENT_TASK=args.task,
                   TEACHER_PROGRESS_URL='http://172.17.0.1:8766/experiment/progress')
    command = [PYTHON, '/tmp/sdk_script.py', '--cwd', '/app', '--base_commit', args.base_commit,
               '--problem_statement_file', args.prompt, '--output_dir', str(args.output),
               '--log_path', str(args.output / 'sdk.log')]
    if args.stage == 'teacher-review':
        assert args.resume_session_id
        command += ['--resume_session_id', args.resume_session_id, '--extra_message_file', args.prompt]
    (args.output / 'sdk_command.json').write_text(json.dumps(command, indent=2))
    try:
        started = time.monotonic()
        with (args.output / 'stdout.log').open('wb') as log:
            process = subprocess.run(command, cwd='/app', env=env, stdout=log,
                                     stderr=subprocess.STDOUT, timeout=3600 if teacher else 7200)
        result['sdk_exit_code'] = process.returncode
        result['elapsed_seconds'] = time.monotonic() - started
        metadata = json.loads((args.output / 'trajs.json').read_text())['metadata']
        result['metadata'] = metadata
        result['sdk_session_id'] = metadata.get('ResultMessage', {}).get('session_id')
        if teacher:
            artifact = Path('/tmp/hint_output.md' if args.stage == 'teacher-initial' else '/tmp/review_output.md')
            if artifact.exists():
                (args.output / artifact.name).write_bytes(artifact.read_bytes())
                result['stage_artifact'] = artifact.name
        result['sdk_completed'] = metadata.get('status') == 'completed' and not metadata.get('ResultMessage', {}).get('is_error', True)
        result['same_sdk_session'] = (result['sdk_session_id'] == args.resume_session_id) if args.resume_session_id else None
        if not teacher:
            state = json.loads((args.output / 'online_teacher_state.json').read_text())
            result['online_teacher_state'] = state
            result['checkpoint_triggered'] = state['checks'] >= 1 and state['tool_count'] >= 20
        result['passed'] = process.returncode == 0 and result['sdk_completed'] and result['same_sdk_session'] is not False
        if not teacher:
            result['passed'] = result['passed'] and result['checkpoint_triggered']
    finally:
        projects = Path('/root/.claude/projects')
        if projects.exists():
            with tarfile.open(args.output / 'sdk_sessions.tar', 'w') as archive:
                archive.add(projects, arcname='projects')
        result['finished_at_unix'] = time.time()
        (args.output / 'stage_result.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result), flush=True)
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
