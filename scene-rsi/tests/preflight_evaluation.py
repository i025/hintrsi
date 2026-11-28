"""Reuse one real delivery and inspect blind RGB inputs without starting any model."""
import argparse
import base64
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
sys.path[:0] = [str(ROOT / 'analysis'), str(ROOT / 'harness')]
import evaluate_student as evaluation
import run_capability_improvement as improvement
from isolation import command
from run_capability_acquisition import write

PROBE = '''import anyio, base64, json, sys
from pathlib import Path
sys.path.insert(0, '/harness')
import sdk_student, run_cc_sdk, codex_cli_bridge
from claude_agent_sdk import ClaudeSDKClient
session = json.loads(Path('/inputs/session.json').read_text())
assert session['role'] == 'visual_evaluator'
assert session['tools'] == ['Read', 'Write']
assert not session['hint_enabled'] and not session['persistent_capability_enabled']
assert not session.get('online_teacher_enabled') and 'condition' not in session
assert sorted(p.name for p in Path('/app').iterdir()) == ['final.png', 'reference.png']
assert sorted(p.name for p in Path('/inputs').iterdir()) == ['images.json', 'prompt.txt', 'session.json']
for path in [sys.argv[1], '/capabilities', '/evidence', '/development_gt', '/dev_gt',
             '/initial', '/analysis', '/candidate_history', '/harness/run_exploration.py']:
    assert not Path(path).exists(), path
async def messages():
    return [item async for item in sdk_student.prompt_messages()]
messages = anyio.run(messages)
content = messages[0]['message']['content']
assert len(content) == 5
assert content[0]['text'] == Path('/inputs/prompt.txt').read_text()
assert [content[1]['text'], content[3]['text']] == ['Reference image', 'Candidate reconstruction']
images = [item['source'] for item in content if item['type'] == 'image']
assert len(images) == 2
for image, name in zip(images, ['reference.png', 'final.png']):
    assert image['media_type'] == 'image/png'
    assert base64.b64decode(image['data']) == (Path('/app') / name).read_bytes()
assert codex_cli_bridge.MODEL == 'gpt-6.1-terra' and codex_cli_bridge.EFFORT == 'low'
options = run_cc_sdk.create_agent_options('/app')
options.tools = session['tools']
client = ClaudeSDKClient(options=options)  # Do not connect or query.
Path('/capture/preflight_sdk_input.json').write_text(json.dumps({'kind': 'constructed_not_sent', 'messages': messages}))
Path('/capture/probe.json').write_text(json.dumps({
    'anonymous_image_count': len(images), 'media_types': [item['media_type'] for item in images],
    'image_bytes_base64': [item['data'] for item in images],
    'tools': options.tools, 'sdk_client_constructed_without_connecting': True,
    'gt_library_history_and_host_project_unavailable': True, 'model_calls': 0}))
'''


def contents(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate-output', type=Path,
                        default=ROOT / 'experiments/capability_improvement/stage_05_evaluation_feedback/prepared_only')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    started = time.monotonic()
    source = ROOT / 'experiments/experiment_03a_capability_acquisition/runs/A-T01-A3'
    argv = evaluation.read(source / 'sdk_command.json')
    library_source = Path(next(argv[i + 1] for i, value in enumerate(argv[:-2])
                               if value == '--ro-bind' and argv[i + 2] == '/capabilities'))
    before = {str(source): contents(source), str(library_source): contents(library_source)}
    fixture = output / 'fixtures/arbitrary.name'
    for folder in ['workspace', 'capture', 'bridge', 'inputs']:
        shutil.copytree(source / folder, fixture / folder)
    for name in ['status.json', 'sdk_command.json']:
        shutil.copy2(source / name, fixture / name)
    shutil.copytree(library_source, fixture / 'library')
    write(fixture / 'run.json', {'status': 'collected', 'run_id': 'arbitrary.name',
        'engineering_compatibility_fixture': True, 'source_student_run': str(source),
        'library_snapshot_provenance': 'Copied from the archived /capabilities mount recorded by this student.',
        'runtime_library': str(fixture / 'library')})
    records = []

    def prepare(name, student, items):
        input_file = output / (name + '_input.json')
        write(input_file, {'student_run': str(student), 'output_directory': str(output / name),
            'items': items, 'budget': {'cpus': [32, 33], 'stage_seconds': 120,
                'visual_seconds': 60, 'visual_calls': 2, 'visual_port': 19865}})
        return evaluation.prepare(input_file)

    complete = prepare('complete', fixture, evaluation.ITEMS)
    results = evaluation.technical(complete)
    assert all(row['status'] == 'completed' for row in results.values()), results
    assert results['reproduction']['result']['source_portable_deliverables']
    assert results['images']['result']['rgba_pixel_identical']
    session = complete / 'visual/session'
    with tempfile.TemporaryDirectory(prefix='scene-evaluation-probe-') as temporary, socket.socket(socket.AF_UNIX) as channel:
        channel.bind(str(Path(temporary) / 'proxy.sock'))
        sdk_command = command(session, Path(temporary) / 'proxy.sock', 2)
        argv = ['nice', '-n', '15', 'taskset', '-c', '32,33'] + sdk_command[:sdk_command.index('--')] + [
            '--', '/opt/python/bin/python3.12', '-c', PROBE, str(ROOT)]
        write(output / 'visual_namespace_command.json', argv)
        with (output / 'visual_namespace.log').open('wb') as log:
            subprocess.run(argv, stdout=log, stderr=subprocess.STDOUT, timeout=60, check=True)
    probe = evaluation.read(session / 'capture/probe.json')
    assert [base64.b64decode(value) for value in probe.pop('image_bytes_base64')] == [
        (complete / 'reference.png').read_bytes(), (fixture / 'workspace/final.png').read_bytes()]
    actual = evaluation.read(session / 'capture/preflight_sdk_input.json')
    assert actual['messages'][0]['message']['content'][0]['text'] == evaluation.VISUAL_PROMPT
    feedback = evaluation.collect(complete)
    assert feedback['visual']['status'] == 'not_run' and feedback['visual']['result'] is None
    assert feedback['student']['delivery']['kind'] == 'complete_files_unvalidated'
    records.append({'case': 'complete_real_delivery_copy', 'student': str(fixture),
                    'feedback': str(complete / 'feedback.json'), 'delivery': feedback['student']['delivery']['kind']})

    partial = output / 'fixtures/partial.engineering'
    shutil.copytree(fixture, partial)
    (partial / 'workspace/scene.blend').unlink()
    write(partial / 'run.json', {'status': 'collected', 'run_id': 'partial.engineering',
          'engineering_derived_partial_fixture': True, 'removed_file': 'workspace/scene.blend',
          'source_student_run': str(source), 'not_a_historical_student_failure': True})
    partial_output = prepare('partial', partial, ['scene', 'images', 'evidence'])
    checks = evaluation.technical(partial_output)
    assert checks['scene']['status'] == 'skipped' and checks['images']['status'] == 'completed'
    partial_feedback = evaluation.collect(partial_output)
    assert partial_feedback['student']['delivery']['kind'] == 'partial'
    records.append({'case': 'derived_partial_fixture_not_student_failure', 'student': str(partial),
                    'feedback': str(partial_output / 'feedback.json')})
    for name in ['a3', 'candidate', 'base']:
        student = ROOT / 'experiments/student_execution/stage_04_code_review/preflight' / name
        before[str(student)] = contents(student)
        directory = prepare('empty_delivery_' + name, student, evaluation.ITEMS)
        checks = evaluation.technical(directory)
        result = evaluation.collect(directory)
        assert result['student']['delivery']['kind'] == 'none'
        assert checks['evidence']['status'] == 'completed'
        assert all(checks[item]['status'] == 'skipped' for item in ['reproduction', 'scene', 'images'])
        assert result['visual']['status'] == 'skipped' and result['visual']['result'] is None
        expected = contents(student / 'library') if (student / 'library').exists() else {}
        assert expected == (contents(Path(evaluation.read(student / 'run.json')['library_source']))
                            if name != 'base' else {})
        records.append({'case': 'ended_stage04_engineering_' + name, 'student': str(student),
            'feedback': str(directory / 'feedback.json'), 'library': result['inputs']['runtime_library_status'],
            'delivery': 'none', 'not_a_research_student_failure': True})
    next_input = output / 'improvement_input.json'
    write(next_input, {'initial_library': str(fixture / 'library'), 'feedback': str(complete / 'feedback.json'),
        'evidence': [str(fixture / 'workspace'), str(fixture / 'capture'), str(complete / 'technical')],
        'development_gt': [], 'history': [], 'budget': {'seconds': 60, 'calls': 2, 'cpus': [32, 33], 'port': 19866}})
    candidate = args.candidate_output.resolve()
    improvement.prepare(candidate, next_input)
    assert (candidate / 'inputs/recorded_feedback.json').read_bytes() == (complete / 'feedback.json').read_bytes()
    assert contents(candidate / 'initial/library') == contents(fixture / 'library')
    session = evaluation.read(candidate / 'inputs/session.json')
    assert '/development_gt' not in [row['target'] for row in session['readonly_mounts']]
    assert not (candidate / 'session').exists() and not (candidate / 'candidate').exists()
    assert all(contents(Path(path)) == original for path, original in before.items())
    write(output / 'verification.json', {'kind': 'engineering_evaluation_preflight_not_research',
        'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'seconds': time.monotonic() - started, 'cases': records, 'visual_input_checks': probe,
        'source_and_original_libraries_unchanged': True, 'historical_delivery_regenerations': 1,
        'source_only_rgba_pixel_identical': True, 'improvement_prepare': str(candidate),
        'feedback_copied_unchanged': True, 'development_gt_mounted': False,
        'new_model_calls': 0, 'new_student_reconstructions': 0,
        'limits': 'The actual two-image SDK input was constructed inside the filesystem namespace but never sent. Visual model dispatch is covered by offline mocks, not a model roundtrip. The partial fixture is derived; empty deliveries are prior engineering probes. No new research outcome, candidate update, validation, promotion or iteration.'})
    print(json.dumps({'verification': str(output / 'verification.json'), 'new_model_calls': 0,
                      'historical_delivery_regenerations': 1, 'seconds': time.monotonic() - started}))


if __name__ == '__main__':
    main()
