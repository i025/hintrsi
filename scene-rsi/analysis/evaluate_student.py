"""Evaluate one ended student with existing technical checks and an optional blind RGB SDK review."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
from run_capability_acquisition import copy_tree, write
from run_capability_improvement import RUNTIME_FILES
from run_sdk_session import execute
from isolation import prepare as prepare_isolated
import evaluate_capability_acquisition as technical_checks
from review_capability_acquisition import VISUAL_PROMPT, session_file
from summarize_run import summarize as summarize_evidence
from usage_summary import summarize as summarize_usage

ITEMS = ['reproduction', 'scene', 'images', 'evidence', 'visual']


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def usage(directory, scope):
    # A missing request log does not establish that no model calls occurred.
    available = {name: (directory / 'bridge' / name).exists()
                 for name in ['model_requests.jsonl', 'token_usage.jsonl']}
    return {'record': summarize_usage(directory, scope, root=directory.parent), 'logs_available': available,
            'total_calls_known': available['model_requests.jsonl'],
            'note': 'Counts describe saved logs; unavailable usage or billing remains unknown.'}


def prepare(input_file):
    input_file = Path(input_file).resolve()
    configuration = read(input_file)
    student = (input_file.parent / configuration['student_run']).resolve()
    output = (input_file.parent / configuration['output_directory']).resolve()
    state, record = read(student / 'status.json', {}), read(student / 'run.json', {})
    if state.get('status') in ('starting', 'running') or record.get('status') in ('prepared', 'started'):
        raise ValueError('Evaluate only an ended student run.')
    if not state and record.get('status') != 'collected':
        raise ValueError('A student completion record is required, including failed attempts.')
    if student == output or student in output.parents:
        raise ValueError('Use a new evaluation directory outside the student run.')
    if set(configuration['items']) - set(ITEMS):
        raise ValueError('Supported existing evaluation items: ' + ', '.join(ITEMS))
    output.mkdir(parents=True)
    shutil.copy2(input_file, output / 'input.json')
    reference = next((path for path in [student / 'inputs/reference.png', student / 'workspace/reference.png']
                      if path.is_file()), None)
    if reference:
        shutil.copy2(reference, output / 'reference.png')
    library = student / 'library'
    evaluation = {'status': 'prepared', 'student_run': str(student), 'run_id': record.get('run_id', student.name),
                  'student_record': record or None, 'supervisor_state': state or None,
                  'reference_source': str(reference) if reference else None,
                  'reference_used': str(output / 'reference.png') if reference else None,
                  'runtime_library': str(library) if library.is_dir() else None,
                  'runtime_library_status': 'snapshot_available' if library.is_dir() else
                      'none' if state.get('persistent_capability_enabled') is False or
                      ('runtime_library' in record and record['runtime_library'] is None) else 'unknown',
                  'items': configuration['items'], 'budget': configuration['budget'],
                  'prepared_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    visual = {'status': 'not_requested', 'result': None}
    if 'visual' in evaluation['items']:
        final = student / 'workspace/final.png'
        if reference is None or not final.is_file() or final.stat().st_size == 0:
            visual = {'status': 'skipped', 'reason': 'Missing actual reference or delivered final.png.', 'result': None}
        else:
            folder = output / 'visual'
            seed = folder / 'seed'
            seed.mkdir(parents=True)
            shutil.copy2(output / 'reference.png', seed / 'reference.png')
            shutil.copy2(final, seed / 'final.png')
            for name in RUNTIME_FILES:
                if name.startswith('sdk/'):
                    destination = folder / 'runtime' / name
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(ROOT / name, destination)
            config = session_file('visual', [{'source': str(folder / 'runtime/sdk'), 'target': '/sdk'}],
                                  visual=True, path=folder / 'session_config.json')
            session = read(config)
            budget = evaluation['budget']
            invocation = {'directory': str(folder / 'session'), 'image': str(seed / 'reference.png'),
                          'checkpoint': str(seed), 'prompt': VISUAL_PROMPT,
                          'seconds': budget['visual_seconds'], 'calls': budget['visual_calls'],
                          'cpus': budget['cpus'], 'port': budget['visual_port'], 'session': session}
            prepare_isolated(invocation['directory'], invocation['image'], invocation['prompt'],
                             invocation['checkpoint'], invocation['session'])
            write(folder / 'invocation.json', invocation)
            visual = {'status': 'prepared', 'result': None, 'invocation': str(folder / 'invocation.json')}
    evaluation['visual'] = visual
    write(output / 'evaluation.json', evaluation)
    return output


def technical(directory):
    directory = Path(directory).resolve()
    if (directory / 'technical.json').exists() or (directory / 'feedback.json').exists():
        raise FileExistsError('Existing evaluation results are not overwritten.')
    evaluation = read(directory / 'evaluation.json')
    student = Path(evaluation['student_run'])
    budget = evaluation['budget']
    cpus = ','.join(map(str, budget['cpus']))
    output = directory / 'technical'
    output.mkdir()
    results = {}
    for item in ITEMS[:-1]:
        if item not in evaluation['items']:
            results[item] = {'status': 'not_requested', 'result': None}
            continue
        missing = []
        if item in ('reproduction', 'scene'):
            required = ['sdk_command.json', 'workspace/' + ('build.py' if item == 'reproduction' else 'scene.blend')]
            missing = [name for name in required if not (student / name).is_file()]
        if item == 'images':
            missing = [name for name in ['reference.png'] if not (directory / name).is_file()]
            missing += ['workspace/final.png'] if not (student / 'workspace/final.png').is_file() else []
        if missing:
            results[item] = {'status': 'skipped', 'missing': missing, 'result': None}
            continue
        started = time.monotonic()
        try:
            if item == 'reproduction':
                value, replica = technical_checks.reproduce(student, output / 'source_only', cpus,
                                                            budget['stage_seconds'])
                status = 'completed' if value['exit_code'] == 0 and not value['timeout'] else 'failed'
            elif item == 'scene':
                original = output / 'original_copy'
                copy_tree(student / 'workspace', original)
                inspection = output / 'original_inspection'
                argv = technical_checks.environment(student, inspection, original)
                invocation = technical_checks.blender(argv, '/analysis/acquisition_scene_metrics.py',
                            ['--input', '/app/scene.blend', '--output', '/capture/original'])
                execution = technical_checks.invoke(invocation, inspection, 'scene_inspection', cpus, budget['stage_seconds'])
                summary = read(inspection / 'capture/original/summary.json')
                value = {'execution': execution, 'scene_facts': summary,
                         'evidence_directory': str(inspection / 'capture/original')}
                status = 'completed' if execution['exit_code'] == 0 and summary is not None else 'failed'
            elif item == 'images':
                value = technical_checks.compare_images(student / 'workspace/final.png',
                            output / 'source_only/replica/final.png', directory / 'reference.png')
                status = 'completed'
            else:
                index = summarize_evidence(student, output=output / 'evidence')
                facts = technical_checks.code_facts(student)
                write(output / 'evidence/code_facts.json', facts)
                value = {'index': str(output / 'evidence/evidence_index.json'),
                         'sdk_events': str(output / 'evidence/sdk_events.json'),
                         'code_facts': str(output / 'evidence/code_facts.json'),
                         'observed_tool_calls': index['tool_calls'],
                         'scope': 'Original student events and executed captures; static calls do not establish execution or library benefit.'}
                status = 'completed'
            results[item] = {'status': status, 'result': value, 'seconds': time.monotonic() - started}
        except Exception as error:
            results[item] = {'status': 'failed', 'result': None,
                             'error': {'type': type(error).__name__, 'message': str(error)},
                             'seconds': time.monotonic() - started}
        write(directory / 'technical.json', results)
    write(directory / 'technical.json', results)
    return results


def visual(directory):
    directory = Path(directory).resolve()
    evaluation = read(directory / 'evaluation.json')
    if (directory / 'feedback.json').exists() or evaluation['visual']['status'] != 'prepared':
        raise ValueError('Use a prepared, unexecuted RGB review.')
    evaluation['visual']['status'] = 'started'
    write(directory / 'evaluation.json', evaluation)
    try:
        execute(**read(directory / 'visual/invocation.json'))
    except Exception as error:
        write(directory / 'visual/execution_error.json', {'type': type(error).__name__, 'message': str(error)})
    finally:
        evaluation['visual']['status'] = 'attempted'
        write(directory / 'evaluation.json', evaluation)


def collect(directory):
    directory = Path(directory).resolve()
    if (directory / 'feedback.json').exists():
        raise FileExistsError('The existing feedback is not overwritten.')
    evaluation = read(directory / 'evaluation.json')
    student = Path(evaluation['student_run'])
    state = read(student / 'status.json')
    metadata = read(student / 'capture/trajs.json', {}).get('metadata', {})
    files = [{'path': str(student / 'workspace' / name), 'exists': (student / 'workspace' / name).is_file(),
              'bytes': (student / 'workspace' / name).stat().st_size if (student / 'workspace' / name).is_file() else None}
             for name in ['build.py', 'scene.blend', 'final.png']]
    present = sum(row['exists'] and row['bytes'] > 0 for row in files)
    review = dict(evaluation['visual'])
    review.update(result=None, human_rating=None)
    if review['status'] in ('started', 'attempted'):
        report = directory / 'visual/session/workspace/visual_evaluation.json'
        review['session_state'] = read(directory / 'visual/session/status.json')
        review['execution_error'] = read(directory / 'visual/execution_error.json')
        review['report'] = str(report)
        try:
            value = read(report)
            review['result'] = value if isinstance(value, dict) else None
            review['status'] = 'reported' if isinstance(value, dict) else 'missing_or_invalid_report'
        except json.JSONDecodeError:
            review['status'] = 'invalid_json_report'
    elif review['status'] == 'prepared':
        review['status'] = 'not_run'
    costs = {'student': usage(student, 'student'),
             'visual': usage(directory / 'visual/session', 'visual_evaluation') if evaluation['visual']['status'] in ('started', 'attempted') else None,
             'technical': {'record': str(directory / 'technical.json'),
                           'note': 'Stage wall times and execution logs are evaluator costs, not student behavior.'}}
    write(directory / 'costs.json', costs)
    library = Path(evaluation['runtime_library']) if evaluation['runtime_library'] else None
    prompt = student / 'inputs/prompt.txt'
    feedback = {'schema_version': 1, 'kind': 'independent_student_evaluation',
        'student': {'run': str(student), 'run_id': evaluation['run_id'], 'record': evaluation['student_record'],
                    'supervisor_state': state, 'sdk_status': metadata.get('status', (state or {}).get('sdk_status')),
                    'delivery': {'kind': 'complete_files_unvalidated' if present == 3 else 'partial' if present else 'none',
                                 'files': files, 'required_files_present': present == 3}},
        'inputs': {'reference_source': evaluation['reference_source'], 'reference_used': evaluation['reference_used'],
                   'runtime_library': str(library) if library else None,
                   'runtime_library_status': evaluation['runtime_library_status'],
                   'skill_in_prepared_prompt': (library / 'SKILL.md').read_text() in prompt.read_text()
                       if library and (library / 'SKILL.md').exists() and prompt.exists() else None},
        'technical': read(directory / 'technical.json', {item: {
            'status': 'not_run' if item in evaluation['items'] else 'not_requested', 'result': None} for item in ITEMS[:-1]}),
        'visual': review, 'costs': costs,
        'student_evidence': {'sdk_trajectory': str(student / 'capture/trajs.json'),
                             'model_requests': str(student / 'bridge/model_requests.jsonl'),
                             'tool_and_blender_captures': str(student / 'capture'),
                             'delivered_source_and_scene': str(student / 'workspace'),
                             'library_snapshot': str(library) if library else None},
        'evaluator_evidence': {'output': str(directory), 'technical': str(directory / 'technical'),
                               'visual': str(directory / 'visual/session')},
        'data_policy': {'outcomes_used_for_improvement': 'historical_development_experience',
                        'future_independent_test': 'Use new held-out scenes after these outcomes inform improvement.'},
        'limits': ['Prepared-prompt knowledge presence, recorded reads, static source calls, actual executions and benefit are distinct evidence.',
                   'Deterministic regeneration/inspection is an evaluator action. RGB judgments are automated model observations, not human ratings.',
                   'Missing or unexecuted judgments remain unknown. No composite score, GT correspondence, promotion or next iteration is implemented.']}
    write(directory / 'feedback.json', feedback)
    evaluation.update(status='collected', collected_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(directory / 'evaluation.json', evaluation)
    return feedback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'technical', 'visual', 'collect', 'run'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.stage == 'prepare':
        if not args.input:
            parser.error('--input is required for prepare')
        print(prepare(args.input))
    else:
        if not args.directory:
            parser.error('--directory is required')
        if args.stage == 'run':
            try:
                technical(args.directory)
                if read(args.directory / 'evaluation.json')['visual']['status'] == 'prepared':
                    visual(args.directory)
            finally:
                collect(args.directory)
        else:
            {'technical': technical, 'visual': visual, 'collect': collect}[args.stage](args.directory)


if __name__ == '__main__':
    main()
