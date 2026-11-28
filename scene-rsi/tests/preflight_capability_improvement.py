"""Use real historical evidence and the real namespace, without starting a model or student."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
from run_capability_acquisition import EXP, PYTHON, write
from run_capability_improvement import collect, EXCLUDED
from isolation import prepare as prepare_isolated, command

PROBE = '''import json, os
from pathlib import Path
feedback = json.loads(Path('/feedback/feedback.json').read_text())
assert feedback['data_policy']['experiment03a_outcomes'] == 'historical_development_experience'
assert len(feedback['student_outcomes']['runs']) == 24
failed = next(row for row in feedback['student_runs'] if row['run'] == 'A-T01-A2')
trajectory = Path(failed['trajectory'])
assert json.loads(trajectory.read_text())['trajectories']['main_agent']
completed = next(row for row in feedback['student_outcomes']['runs'] if row['complete_delivery'])
run = next(row for row in feedback['student_runs'] if row['run'] == completed['run'])
assert (Path(run['code_scene_and_render'])/'final.png').read_bytes()[:8] == b'\\x89PNG\\r\\n\\x1a\\n'
assert (Path(run['code_scene_and_render'])/'scene.blend').stat().st_size > 0
assert (Path(run['code_scene_and_render'])/'build.py').read_text()
readonly = {}
for path in ['/initial/library/SKILL.md', str(trajectory), feedback['allowed_development_gt'][0]['blend']]:
    try:
        descriptor = os.open(path, os.O_WRONLY)
    except OSError:
        readonly[path] = True
    else:
        os.close(descriptor)
        readonly[path] = False
assert all(readonly.values()), readonly
assert not Path(feedback['path_mapping']['host_root']).exists()
split = json.loads(Path(feedback['data_policy']['historical_split']).read_text())
for scene in split['test']:
    assert not Path(scene['blend'].replace(feedback['path_mapping']['host_root'], '/evidence')).exists()
Path('/app/library/ENGINEERING_PROBE.md').write_text('Engineering namespace write probe only. Not a model-generated capability or research result.\\n')
Path('/app/engineering_probe.json').write_text(json.dumps({'actual_feedback_read': True, 'actual_student_trajectory_read': True, 'actual_code_scene_and_render_read': True, 'readonly_open_checks': readonly, 'host_project_not_mounted': True, 'former_test_gt_not_mounted': True, 'candidate_write_succeeded': True, 'model_requests': 0}, indent=2))
'''


def inventory():
    records = {}
    for name in ['experiment_01_natural_trajectories', 'experiment_02_teacher_guided_exploration',
                 'experiment_03a_capability_acquisition', 'experiment_03b_teacher_alignment']:
        base = ROOT / 'experiments' / name
        for path in base.rglob('*'):
            if path.is_file() and not path.is_symlink() and not EXCLUDED.intersection(path.relative_to(base).parts):
                stat = path.stat()
                records[str(path.relative_to(ROOT))] = (stat.st_size, stat.st_mtime_ns)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-repository', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    before = inventory()
    libraries = {str(p): p.read_bytes() for p in (EXP / 'libraries').rglob('*') if p.is_file()}
    started = time.monotonic()
    candidate = output / 'offline_candidate'
    argv = [PYTHON, '-B', str(ROOT / 'harness/run_capability_improvement.py'), 'prepare',
            '--directory', str(candidate), '--condition', 'A3', '--seconds', '90', '--calls', '3']
    write(output / 'prepare_command.json', argv)
    with (output / 'prepare.log').open('wb') as log:
        subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=True)
    invocation = json.loads((candidate / 'inputs/invocation.json').read_text())
    prepare_isolated(invocation['directory'], invocation['image'], invocation['prompt'],
                     invocation['checkpoint'], invocation['session'])
    with tempfile.TemporaryDirectory(prefix='scene-feedback-probe-') as temporary, socket.socket(socket.AF_UNIX) as channel:
        channel.bind(str(Path(temporary) / 'proxy.sock'))
        argv = command(candidate / 'session', Path(temporary) / 'proxy.sock', 3)
        argv = argv[:argv.index('--')] + ['--', '/opt/python/bin/python3.12', '-c', PROBE]
        argv = ['nice', '-n', '15', 'taskset', '-c', '32,33'] + argv
        write(output / 'namespace_command.json', argv)
        with (output / 'namespace.log').open('wb') as log:
            subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
    probe = json.loads((candidate / 'session/workspace/engineering_probe.json').read_text())
    write(candidate / 'session/status.json', {'status': 'offline_engineering_probe',
          'agent_loop_started': False, 'model_requests': 0, 'owned_processes_stopped': True})
    record = collect(candidate)
    assert record['agent_decision'] is None and record['promotion_status'] == 'not_promoted'
    assert (candidate / 'candidate/library/ENGINEERING_PROBE.md').exists()
    assert all(Path(path).read_bytes() == content for path, content in libraries.items())
    after = inventory()
    differences = [path for path in before.keys() | after.keys() if before.get(path) != after.get(path)]
    assert not differences, differences
    unchanged = []
    if args.baseline_repository:
        for path in ['harness/run_capability_acquisition.py', 'harness/run_sdk_session.py',
                     'harness/sdk_student.py', 'harness/run_exploration.py', 'sdk/run_cc_sdk.py',
                     'sdk/codex_cli_bridge.py', 'analysis/evaluate_capability_acquisition.py']:
            original = subprocess.check_output(['git', '-C', str(args.baseline_repository), 'show',
                                                'ad837c5:scene-rsi/' + path])
            assert original == (ROOT / path).read_bytes(), path
            unchanged.append(path)
    summary = {'kind': 'offline_engineering_preflight_not_research',
               'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'seconds': time.monotonic() - started, 'checks': probe,
               'candidate_library_diff': str(candidate / 'candidate/library.diff'),
               'agent_report_status': record['report_status'],
               'candidate_promotion_status': record['promotion_status'],
               'historical_files_checked': len(before), 'historical_file_size_or_mtime_differences': differences,
               'frozen_library_bytes_unchanged': True, 'existing_execution_sources_unchanged': unchanged,
               'sdk_or_bridge_started': False, 'new_model_calls': 0, 'new_student_reconstructions': 0,
               'new_downloads_or_environment_installs': 0, 'gpu_used': False,
               'limits': 'The library marker was written by the engineering probe, not an improvement model. Unit tests mock execute() to verify SDK dispatch and collection. Model autonomy and candidate benefit have not been tested.'}
    write(output / 'verification.json', summary)
    shutil.copy2(candidate / 'inputs/feedback.json', output / 'feedback_example.json')
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
