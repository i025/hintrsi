"""Check real source visibility in the existing namespace without model requests."""
import argparse
import datetime
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
from run_capability_acquisition import EXP, PYTHON, write
from run_capability_improvement import prepare, collect, RUNTIME_FILES
from isolation import prepare as prepare_isolated, command

HISTORICAL = ['analysis/annotate_experiment.py', 'analysis/write_report.py',
              'analysis/write_exploration_report.py', 'harness/run_exploration.py']
PROBE = '''import json, os, subprocess, sys
from pathlib import Path
feedback = json.loads(Path('/feedback/feedback.json').read_text())
assert json.loads(Path(feedback['recorded_feedback']).read_text())['runs']
runtime = Path('/initial/system')
visible = sorted(str(path.relative_to(runtime)) for path in runtime.rglob('*') if path.is_file())
assert visible == sorted(feedback['components']['runtime_source_files'])
hidden = ['analysis/annotate_experiment.py', 'analysis/write_report.py',
          'analysis/write_exploration_report.py', 'harness/run_exploration.py']
for name in hidden:
    assert not (runtime / name).exists()
    assert not Path('/' + name).exists()
assert not (runtime / 'sdk/run_cc_sdk_vs_parallel13.diff').exists()
assert not Path('/sdk/run_cc_sdk_vs_parallel13.diff').exists()
assert not Path(feedback['components']['source_library']).exists()
assert not Path(feedback['feedback_source']).exists()
assert not Path('/development_gt').exists()
assert not Path('/candidate_history').exists()
evidence = json.loads(Path('/feedback/evidence_index.json').read_text())['files']
assert len(evidence) == len(feedback['allowed_evidence'])
for row in evidence:
    path = Path(row['path'])
    assert row['available'] and path.stat().st_size == row['bytes']
    compile(path.read_text(), str(path), 'exec')  # Read the source; do not run historical analysis.
    assert 'SEQUENCES' in path.read_text()
readonly = [Path('/initial/library/SKILL.md'), runtime / 'sdk/run_cc_sdk.py']
readonly += [Path(row['path']) for row in evidence]
for path in readonly:
    try:
        descriptor = os.open(path, os.O_WRONLY)
    except OSError:
        pass
    else:
        os.close(descriptor)
        raise AssertionError('Read-only input is writable: ' + str(path))
os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['LITELLM_TELEMETRY'] = 'False'
sys.path.insert(0, '/harness')
import sdk_student, run_cc_sdk, codex_cli_bridge, claude_code_proxy
from claude_agent_sdk import ClaudeSDKClient
assert codex_cli_bridge.MODEL == 'gpt-6.1-terra' and codex_cli_bridge.EFFORT == 'low'
options = run_cc_sdk.create_agent_options('/app')
options.tools = json.loads(Path('/inputs/session.json').read_text())['tools']
assert options.tools == ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep']
client = ClaudeSDKClient(options=options)  # No connect/query; no agent or model session starts.
subprocess.run(['/bin/bash', '-c', "printf 'Engineering filesystem probe only.\\n' > /app/library/ENGINEERING_PROBE_03.md"], check=True)
assert Path('/app/library/ENGINEERING_PROBE_03.md').read_text().startswith('Engineering')
result = {'runtime_files': visible, 'historical_sources_hidden_by_default': hidden,
          'explicit_evidence_read': [row['path'] for row in evidence],
          'readonly_inputs_checked': len(readonly), 'sdk_entry_and_bridge_imported': True,
          'sdk_client_constructed_without_connecting': True, 'tools': options.tools,
          'candidate_write_succeeded': True, 'new_model_calls': 0}
Path('/app/visibility_probe.json').write_text(json.dumps(result, indent=2))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    started = time.monotonic()
    sources = [path for folder in ['sdk', 'harness', 'analysis']
               for path in (ROOT / folder).rglob('*') if path.is_file() and path.suffix != '.pyc']
    library = EXP / 'libraries/A3'
    feedback_file = EXP / 'analysis/observed_results.json'
    preserved = {path: path.read_bytes() for path in sources + list(library.iterdir()) + [feedback_file]}
    records = []
    for name, evidence in [('empty', []), ('explicit_analysis', [str(ROOT / HISTORICAL[0])])]:
        input_file = output / (name + '_input.json')
        write(input_file, {'initial_library': str(library), 'feedback': str(feedback_file),
                          'evidence': evidence, 'development_gt': [], 'history': [],
                          'budget': {'seconds': 60, 'calls': 1, 'cpus': [32, 33], 'port': 19665}})
        candidate = output / name
        prepare(candidate, input_file)
        for path in sources:
            assert (candidate / 'initial/system' / path.relative_to(ROOT)).read_bytes() == preserved[path]
        invocation = json.loads((candidate / 'inputs/invocation.json').read_text())
        prepare_isolated(invocation['directory'], invocation['image'], invocation['prompt'],
                         invocation['checkpoint'], invocation['session'])
        with tempfile.TemporaryDirectory(prefix='scene-runtime-probe-') as temporary, socket.socket(socket.AF_UNIX) as channel:
            channel.bind(str(Path(temporary) / 'proxy.sock'))
            argv = command(candidate / 'session', Path(temporary) / 'proxy.sock', 1)
            argv = ['nice', '-n', '15', 'taskset', '-c', '32,33'] + argv[:argv.index('--')] + [
                    '--', '/opt/python/bin/python3.12', '-c', PROBE]
            write(output / (name + '_command.json'), argv)
            with (output / (name + '.log')).open('wb') as log:
                subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=60, check=True)
        write(candidate / 'session/status.json', {'status': 'offline_visibility_probe', 'model_requests': 0})
        record = collect(candidate)
        assert record['file_changes'] == [{'path': 'ENGINEERING_PROBE_03.md', 'kind': 'added'}]
        assert record['promotion_status'] == 'not_promoted' and record['agent_decision'] is None
        records.append({'name': name, 'candidate': str(candidate),
                        'checks': json.loads((candidate / 'session/workspace/visibility_probe.json').read_text()),
                        'host_archive_files_checked': len(sources), 'collection': record})
    assert all(path.read_bytes() == content for path, content in preserved.items())
    result = {'kind': 'offline_runtime_visibility_check_not_research',
              'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'seconds': time.monotonic() - started, 'attempts': records,
              'source_library_feedback_bytes_unchanged': True, 'default_runtime_files': RUNTIME_FILES,
              'new_model_calls': 0, 'new_student_reconstructions': 0,
              'limits': 'SDK imports and client construction were checked without connecting. Bash and file writes were exercised in the real namespace. No model-guided SDK tool roundtrip or capability improvement was tested.'}
    write(output / 'verification.json', result)
    print(json.dumps({'verification': str(output / 'verification.json'), 'seconds': result['seconds'],
                      'attempts': len(records), 'runtime_files': len(RUNTIME_FILES), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
