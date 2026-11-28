"""Exercise real student inputs, image messages and isolated tools without a model or reconstruction."""
import argparse
import base64
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
from run_student import collect
from isolation import command

PREVIOUS = ROOT / 'experiments/capability_improvement/stage_01_verified_review/offline_candidate/candidate/library'
PROBE = '''import base64, json, os, subprocess, sys
from pathlib import Path
import anyio
sys.path.insert(0, '/harness')
import sdk_student, run_cc_sdk, codex_cli_bridge
from claude_agent_sdk import ClaudeSDKClient
session = json.loads(Path('/inputs/session.json').read_text())
assert session['role'] == 'student' and not session['hint_enabled'] and not session['online_teacher_enabled']
assert sorted(path.name for path in Path('/app').iterdir()) == ['reference.png']
assert not Path('/inputs/input.json').exists()
assert not Path(sys.argv[1]).exists()  # Complete host project, including GT and old experiments.
for path in ['/dev_gt', '/development_gt', '/evidence', '/candidate_history', '/initial', '/analysis', '/harness/run_exploration.py', '/sdk/run_cc_sdk_vs_parallel13.diff']:
    assert not Path(path).exists(), path
async def initial_messages():
    return [message async for message in sdk_student.prompt_messages()]
messages = anyio.run(initial_messages)
content = messages[0]['message']['content']
assert content[0]['text'] == Path('/inputs/prompt.txt').read_text()
image = next(part['source'] for part in content if part['type'] == 'image')
assert image['media_type'] == 'image/png'
image_bytes = base64.b64decode(image['data'])
assert image_bytes == Path('/app/reference.png').read_bytes() == Path('/inputs/reference.png').read_bytes()
library = Path('/capabilities')
assert library.exists() == session['persistent_capability_enabled']
files = {}
if library.exists():
    assert (library/'SKILL.md').read_text() in content[0]['text']
    for path in library.rglob('*'):
        if path.is_file():
            files[str(path.relative_to(library))] = base64.b64encode(path.read_bytes()).decode()
    try:
        descriptor = os.open(library/'SKILL.md', os.O_WRONLY)
    except OSError:
        pass
    else:
        os.close(descriptor)
        raise AssertionError('Capability library is writable')
else:
    assert 'Frozen general capability knowledge:' not in content[0]['text']
assert codex_cli_bridge.MODEL == 'gpt-6.1-terra' and codex_cli_bridge.EFFORT == 'low'
options = run_cc_sdk.create_agent_options('/app')
options.tools = session['tools']
assert options.tools == ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep']
client = ClaudeSDKClient(options=options)  # Never connect or query.
subprocess.run(['/bin/bash', '-c', "printf 'Engineering only\\n' > /app/engineering_probe.txt"], check=True)
path = Path('/app/engineering_probe.txt')
path.write_text(path.read_text().replace('only', 'write/edit probe'))
assert 'write/edit' in path.read_text()
blender = subprocess.run(['blender', '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
assert b'Blender 5.2.2' in blender.stdout
Path('/capture/preflight_sdk_input.json').write_text(json.dumps({'kind': 'constructed_sdk_input_not_sent', 'messages': messages}, indent=2))
Path('/capture/student_probe.json').write_text(json.dumps({
    'actual_sdk_reference_bytes': len(image_bytes), 'skill_injected': library.exists(),
    'library_files_base64': files, 'sdk_client_constructed_without_connecting': True,
    'tools': options.tools, 'host_gt_and_research_unavailable': True,
    'bash_read_write_edit_succeeded': True, 'blender_version_command_succeeded': True,
    'new_model_calls': 0, 'new_reconstructions': 0}, indent=2))
'''


def contents(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    started = time.monotonic()
    reference = Path(json.loads((ROOT / 'configs/scenes.json').read_text())['scenes'][0]['reference'])
    image_before = reference.read_bytes()
    libraries = {'a3': EXP / 'libraries/A3', 'candidate': PREVIOUS, 'base': None}
    originals = {str(path): contents(path) for path in libraries.values() if path is not None}
    records = []
    for name, library in libraries.items():
        run = output / name
        configuration = {'run_id': name, 'output_directory': str(run), 'reference_image': str(reference),
                         'capability_library': str(library) if library else None,
                         'budget': {'seconds': 60, 'calls': 1, 'cpus': [32, 33], 'port': 19665}}
        input_file = output / (name + '_input.json')
        write(input_file, configuration)
        argv = [PYTHON, '-B', str(ROOT / 'harness/run_student.py'), 'prepare', '--input', str(input_file)]
        write(output / (name + '_prepare_command.json'), argv)
        with (output / (name + '_prepare.log')).open('wb') as log:
            subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, check=True)
        assert (run / 'inputs/reference.png').read_bytes() == image_before
        assert contents(run / 'library') == (originals[str(library)] if library else {})
        with tempfile.TemporaryDirectory(prefix='scene-student-probe-') as temporary, socket.socket(socket.AF_UNIX) as channel:
            channel.bind(str(Path(temporary) / 'proxy.sock'))
            sdk_command = command(run, Path(temporary) / 'proxy.sock', 1)
            write(run / 'sdk_command.json', sdk_command)
            argv = ['nice', '-n', '15', 'taskset', '-c', '32,33'] + sdk_command[:sdk_command.index('--')] + [
                    '--', '/opt/python/bin/python3.12', '-c', PROBE, str(ROOT)]
            write(output / (name + '_namespace_command.json'), argv)
            with (output / (name + '_namespace.log')).open('wb') as log:
                subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=60, check=True)
        probe = json.loads((run / 'capture/student_probe.json').read_text())
        exposed = {path: base64.b64decode(value) for path, value in probe.pop('library_files_base64').items()}
        assert exposed == (originals[str(library)] if library else {})
        write(run / 'status.json', {'status': 'offline_engineering_preflight', 'model_requests': 0,
                                   'sdk_command_kind': 'constructed_not_executed', 'model_agent_started': False})
        result = collect(run)
        assert result['delivery']['status'] == 'missing_files' and result['sdk_status'] is None
        assert result['candidate_promotion'] == 'not_performed'
        records.append({'run': str(run), 'checks': probe, 'runtime_library_matches_selected_source': True,
                        'blender_capture_records': len(list((run / 'capture').glob('blender_*'))),
                        'delivery_status': result['delivery']['status']})
    assert reference.read_bytes() == image_before
    assert all(contents(Path(path)) == original for path, original in originals.items())
    result = {'kind': 'offline_student_entry_preflight_not_research',
              'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'seconds': time.monotonic() - started, 'runs': records,
              'reference_and_source_libraries_unchanged': True,
              'new_model_calls': 0, 'new_reconstructions': 0,
              'limits': 'The actual SDK image/text input was constructed and saved but not sent. SDK client construction and isolated filesystem/Blender --version were exercised; no model-guided SDK tool roundtrip, scene generation, evaluation or candidate promotion occurred.'}
    write(output / 'verification.json', result)
    print(json.dumps({'verification': str(output / 'verification.json'), 'seconds': result['seconds'],
                      'runs': len(records), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
