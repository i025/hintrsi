"""Exercise external inputs with real archives and filesystem isolation; no model or Blender execution."""
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
from prepare_improvement_03a import configuration
from run_capability_improvement import collect, EXCLUDED
from isolation import prepare as prepare_isolated, command

PREVIOUS = ROOT / 'experiments/capability_improvement/stage_01_verified_review/offline_candidate'
PROBE = '''import json, os
from pathlib import Path
feedback = json.loads(Path('/feedback/feedback.json').read_text())
observed = json.loads(Path(feedback['recorded_feedback']).read_text())
assert len(observed['runs']) == 24
assert feedback['data_policy']['used_outcomes'] == 'historical_development_experience'
index = json.loads(Path(feedback['evidence_index']).read_text())
readonly = []
for row in index['files']:
    if not row['available']:
        continue
    path = Path(row['path'])
    assert path.is_file(), str(path)
    assert path.stat().st_size == row['bytes']
    if path.name == 'trajs.json':
        assert json.loads(path.read_text())['trajectories']['main_agent']
    if path.name == 'final.png':
        assert path.read_bytes()[:8] == b'\\x89PNG\\r\\n\\x1a\\n'
    try:
        descriptor = os.open(path, os.O_WRONLY)
    except OSError:
        readonly.append(str(path))
    else:
        os.close(descriptor)
        raise AssertionError('Evidence is writable: ' + str(path))
for path in [Path('/initial/library/SKILL.md'), Path('/feedback/recorded_feedback.json')]:
    try:
        descriptor = os.open(path, os.O_WRONLY)
    except OSError:
        readonly.append(str(path))
    else:
        os.close(descriptor)
        raise AssertionError('Initial input is writable: ' + str(path))
assert not Path(feedback['components']['source_library']).exists()
assert not Path(feedback['feedback_source']).exists()
assert not Path('/initial/system/configs/scenes.json').exists()
assert not Path('/initial/system/configs/experiment_01.json').exists()
assert Path('/development_gt').exists() == bool(feedback['allowed_development_gt'])
assert Path('/candidate_history').exists() == bool(feedback['candidate_history'])
assert not Path('/evidence/experiments/experiment_03a_capability_acquisition/libraries/A4').exists()
if 'stage_01_verified_review' in feedback['components']['source_library']:
    assert Path('/app/library/ENGINEERING_PROBE.md').exists()
    assert not feedback['allowed_evidence'] and not feedback['allowed_development_gt'] and not feedback['candidate_history']
Path('/app/library/ENGINEERING_PROBE_02.md').write_text('External-input engineering write probe. Not a model-generated capability or research result.\\n')
Path('/app/engineering_probe.json').write_text(json.dumps({'feedback_read': True, 'available_evidence_files_read': len(readonly)-2, 'readonly_files_checked': len(readonly), 'gt_mount_present': bool(feedback['allowed_development_gt']), 'history_mount_present': bool(feedback['candidate_history']), 'host_source_paths_unavailable': True, 'unselected_historical_configurations_unavailable': True, 'candidate_write_succeeded': True, 'model_requests': 0}, indent=2))
'''


def inventory():
    records = {}
    names = ['experiment_01_natural_trajectories', 'experiment_02_teacher_guided_exploration',
             'experiment_03a_capability_acquisition', 'experiment_03b_teacher_alignment',
             'capability_improvement/stage_01_verified_review']
    for name in names:
        base = ROOT / 'experiments' / name
        for path in base.rglob('*'):
            if path.is_file() and not path.is_symlink() and not EXCLUDED.intersection(path.relative_to(base).parts):
                stat = path.stat()
                records[str(path.relative_to(ROOT))] = (stat.st_size, stat.st_mtime_ns)
    return records


def library_files(path):
    return {str(file.relative_to(path)): file.read_bytes() for file in path.rglob('*') if file.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--baseline-repository', type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    before = inventory()
    libraries = {str(path): library_files(path) for path in [EXP / 'libraries/A3', PREVIOUS / 'candidate/library']}
    started = time.monotonic()
    observed = json.loads((EXP / 'analysis/observed_results.json').read_text())
    complete = next(row for row in observed['runs'] if row['complete_delivery'])['run']
    evidence = [EXP / 'runs/A-T01-A2/capture/trajs.json', EXP / 'runs' / complete / 'workspace',
                EXP / 'runs' / complete / 'analysis']
    limited = configuration('A3', evidence=evidence, seconds=90, calls=3, cpus=[32, 33])
    expanded = dict(limited, evidence=limited['evidence'] + [str(EXP / 'learning/A3/capture/trajs.json'),
                    str(EXP / 'validation/A3/workspace/validation_report.json'),
                    str(EXP / 'analysis/final_usage_summary.json')],
                    development_gt=[json.loads((EXP / 'configs/data_split.json').read_text())['development'][0]['evaluation_directory']],
                    history=[str(PREVIOUS / 'candidate.json'), str(PREVIOUS / 'candidate/costs.json')])
    previous = dict(limited, initial_library=str(PREVIOUS / 'candidate/library'), evidence=[],
                    development_gt=[], history=[], context={'note': 'Prior library is an offline engineering candidate, not a learned improvement.'})
    results = []
    for name, configuration_input in [('a3_limited', limited), ('a3_expanded', expanded), ('previous_candidate', previous)]:
        input_file = output / 'inputs' / (name + '.json')
        write(input_file, configuration_input)
        candidate = output / name
        argv = [PYTHON, '-B', str(ROOT / 'harness/run_capability_improvement.py'), 'prepare',
                '--directory', str(candidate), '--input', str(input_file)]
        write(output / (name + '_prepare_command.json'), argv)
        with (output / (name + '_prepare.log')).open('wb') as log:
            subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=True)
        initial = library_files(Path(configuration_input['initial_library']))
        assert library_files(candidate / 'initial/library') == initial
        assert library_files(candidate / 'seed/library') == initial
        invocation = json.loads((candidate / 'inputs/invocation.json').read_text())
        assert invocation['image'] is None
        prepare_isolated(invocation['directory'], invocation['image'], invocation['prompt'],
                         invocation['checkpoint'], invocation['session'])
        with tempfile.TemporaryDirectory(prefix='scene-feedback-probe-') as temporary, socket.socket(socket.AF_UNIX) as channel:
            channel.bind(str(Path(temporary) / 'proxy.sock'))
            argv = command(candidate / 'session', Path(temporary) / 'proxy.sock', 3)
            argv = argv[:argv.index('--')] + ['--', '/opt/python/bin/python3.12', '-c', PROBE]
            argv = ['nice', '-n', '15', 'taskset', '-c', '32,33'] + argv
            write(output / (name + '_namespace_command.json'), argv)
            with (output / (name + '_namespace.log')).open('wb') as log:
                subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=90, check=True)
        checks = json.loads((candidate / 'session/workspace/engineering_probe.json').read_text())
        write(candidate / 'session/status.json', {'status': 'offline_engineering_probe',
              'agent_loop_started': False, 'model_requests': 0, 'owned_processes_stopped': True})
        record = collect(candidate)
        assert record['agent_decision'] is None and record['promotion_status'] == 'not_promoted'
        assert record['file_changes'] == [{'path': 'ENGINEERING_PROBE_02.md', 'kind': 'added'}]
        results.append({'input': str(input_file), 'candidate': str(candidate), 'checks': checks,
                        'initial_copy_matches_selected_library': True,
                        'changes': record['file_changes'], 'promotion_status': record['promotion_status']})
    assert all(library_files(Path(path)) == contents for path, contents in libraries.items())
    after = inventory()
    differences = [path for path in before.keys() | after.keys() if before.get(path) != after.get(path)]
    assert not differences, differences
    unchanged = []
    if args.baseline_repository:
        for path in ['harness/run_capability_acquisition.py', 'harness/run_sdk_session.py',
                     'harness/sdk_student.py', 'harness/run_exploration.py', 'sdk/run_cc_sdk.py',
                     'sdk/codex_cli_bridge.py', 'analysis/evaluate_capability_acquisition.py', 'analysis/usage_summary.py']:
            original = subprocess.check_output(['git', '-C', str(args.baseline_repository), 'show',
                                                '2ac0342:scene-rsi/' + path])
            assert original == (ROOT / path).read_bytes(), path
            unchanged.append(path)
    summary = {'kind': 'offline_external_input_preflight_not_research',
               'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
               'seconds': time.monotonic() - started, 'attempts': results,
               'historical_files_checked': len(before), 'historical_file_size_or_mtime_differences': differences,
               'original_and_previous_library_bytes_unchanged': True,
               'existing_execution_sources_unchanged': unchanged,
               'sdk_or_bridge_started': False, 'new_model_calls': 0, 'new_student_reconstructions': 0,
               'new_downloads_or_environment_installs': 0, 'gpu_used': False,
               'limits': 'Engineering probes wrote markers, not capabilities. SDK dispatch is mocked in unit tests; model autonomy and candidate benefit were not tested. Explicit evidence/feedback may itself contain GT-derived knowledge; empty GT means no additional GT source mount, not removal of prior knowledge.'}
    write(output / 'verification.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
