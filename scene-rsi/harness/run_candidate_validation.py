"""Compare two external libraries through the existing Student and Evaluation entries."""
import argparse
from collections import Counter
import datetime
import json
import math
from pathlib import Path
import shutil
import sys

from isolation import ROOT
from run_capability_acquisition import copy_tree, write
import run_student as student

sys.path.insert(0, str(ROOT / 'analysis'))
import evaluate_student as evaluation

VERSIONS = ['parent', 'candidate']


def read(path, default=None):
    return json.loads(path.read_text()) if path.is_file() else default


def prepare(input_file):
    input_file = Path(input_file).resolve()
    configuration = read(input_file)

    def resolve(value):
        return (input_file.parent / value).resolve()

    directory = resolve(configuration['output_directory'])
    sources = {name: resolve(configuration[name + '_library']) if configuration.get(name + '_library') else None
               for name in VERSIONS}
    if any(path and (directory == path or path in directory.parents) for path in sources.values()):
        raise ValueError('Use a new output directory outside both input libraries.')
    if configuration['repetitions'] < 1 or not configuration['tasks']:
        raise ValueError('Provide tasks and at least one repetition.')
    if set(configuration['evaluation']['items']) - set(evaluation.ITEMS):
        raise ValueError('Use the existing Evaluation item names.')
    directory.mkdir(parents=True)
    shutil.copy2(input_file, directory / 'input.json')
    libraries = {}
    for name, source in sources.items():
        snapshot = directory / 'libraries' / name
        available = source is not None and source.is_dir()
        if available:
            copy_tree(source, snapshot)
        libraries[name] = {'source': str(source) if source else None,
                           'snapshot': str(snapshot) if available else None,
                           'status': 'available' if available else 'unavailable',
                           'files': [{'path': str(path.relative_to(snapshot)), 'bytes': path.stat().st_size}
                                     for path in sorted(snapshot.rglob('*')) if path.is_file()]}
    changes, change_status = [], 'unknown'
    if all(row['status'] == 'available' for row in libraries.values()):
        parent, candidate = [Path(libraries[name]['snapshot']) for name in VERSIONS]
        names = {str(path.relative_to(parent)) for path in parent.rglob('*') if path.is_file()}
        names |= {str(path.relative_to(candidate)) for path in candidate.rglob('*') if path.is_file()}
        for name in sorted(names):
            a, b = parent / name, candidate / name
            if (a.read_bytes() if a.is_file() else None) != (b.read_bytes() if b.is_file() else None):
                changes.append({'path': name, 'kind': 'added' if not a.is_file() else 'removed' if not b.is_file() else 'modified'})
        change_status = 'changed' if changes else 'unchanged'
    provenance = configuration.get('candidate_record')
    candidate_record = None
    if provenance:
        source = resolve(provenance)
        candidate_record = {'source': str(source), 'record': read(source), 'available': source.is_file()}
        if source.is_file():
            shutil.copy2(source, directory / 'candidate_source_record.json')
    tasks = []
    jobs = []
    for index, task in enumerate(configuration['tasks'], 1):
        image = resolve(task['reference_image'])
        reference = directory / 'references' / ('T' + str(index).zfill(3) + '.png')
        reference.parent.mkdir(exist_ok=True)
        shutil.copy2(image, reference)
        tasks.append({'task_index': index, 'task_id': task['id'], 'reference_source': str(image),
                      'reference_snapshot': str(reference)})
        for repeat in range(1, configuration['repetitions'] + 1):
            pair_id = 'T' + str(index).zfill(3) + '-R' + str(repeat).zfill(2)
            # Balance first/second order in advance; never select order from results.
            order = VERSIONS if len(jobs) // 2 % 2 == 0 else list(reversed(VERSIONS))
            for version in order:
                job_id = pair_id + '-V' + str(VERSIONS.index(version) + 1)
                run = directory / 'students' / job_id
                output = directory / 'evaluations' / job_id
                student_input = directory / 'configs' / (job_id + '-student.json')
                evaluation_input = directory / 'configs' / (job_id + '-evaluation.json')
                write(student_input, {'run_id': job_id, 'output_directory': str(run),
                    'reference_image': str(reference), 'capability_library': str(directory / 'libraries' / version),
                    'budget': configuration['student_budget']})
                write(evaluation_input, {'student_run': str(run), 'output_directory': str(output),
                    'items': configuration['evaluation']['items'], 'budget': configuration['evaluation']['budget']})
                job = {'job_id': job_id, 'pair_id': pair_id, 'task_index': index, 'task_id': task['id'],
                       'repeat': repeat, 'version': version, 'student_input': str(student_input),
                       'evaluation_input': str(evaluation_input), 'student_run': str(run),
                       'evaluation_directory': str(output), 'errors': []}
                if libraries[version]['status'] != 'available':
                    job['status'] = 'library_unavailable'
                else:
                    try:
                        student.prepare(student_input)
                        job['status'] = 'prepared'
                    except Exception as error:
                        job['status'] = 'preparation_failed'
                        job['errors'].append({'stage': 'student_prepare', 'type': type(error).__name__, 'message': str(error)})
                jobs.append(job)
    record = {'status': 'prepared', 'prepared_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'libraries': libraries, 'library_comparison': {'status': change_status, 'file_changes': changes},
              'candidate_source_record': candidate_record, 'tasks': tasks,
              'context': configuration.get('context', {}),
              'repetitions': configuration['repetitions'], 'student_budget': configuration['student_budget'],
              'evaluation': configuration['evaluation'], 'model': 'gpt-6.1-terra', 'reasoning_effort': 'low',
              'execution_order': 'Sequential; alternate parent-first and candidate-first by planned pair.',
              'jobs': jobs, 'promotion_status': 'not_performed',
              'data_policy': 'Development/selection tasks, never final independent tests after use for improvement or selection.'}
    write(directory / 'validation.json', record)
    return directory


def metrics(feedback):
    technical = (feedback or {}).get('technical', {})
    image_result = technical.get('images', {}).get('result') or {}
    reference = image_result.get('reference_comparison') or {}
    visual = (feedback or {}).get('visual', {}).get('result') or {}
    return {'auxiliary_ssim': reference.get('ssim_rgb_gaussian_auxiliary'),
            'mae_rgb': reference.get('mae_rgb'),
            'model_visual_estimate_0_100': visual.get('overall_fidelity_estimate_0_100')}


def observed_side(job, library):
    run, output = Path(job['student_run']), Path(job['evaluation_directory'])
    result = read(run / 'result.json')
    feedback = read(output / 'feedback.json')
    record = read(run / 'run.json')
    return {'attempt': job, 'library': library, 'actual_student_record': record,
            'student_result': result, 'supervisor_state': read(run / 'status.json'),
            'evaluation_feedback': feedback, 'metrics': metrics(feedback),
            'costs': feedback['costs'] if feedback else {'student_saved_record': read(run / 'costs.json'),
                                                       'evaluation': None},
            'evidence': {'student': str(run), 'student_input': job['student_input'],
                         'runtime_library': record.get('runtime_library') if record else None,
                         'trajectory': str(run / 'capture/trajs.json'), 'blender_captures': str(run / 'capture'),
                         'model_logs': str(run / 'bridge'), 'evaluation': str(output),
                         'evaluation_feedback': str(output / 'feedback.json')}}


def collect(directory):
    directory = Path(directory).resolve()
    if (directory / 'comparison.json').exists() or (directory / 'feedback.json').exists():
        raise FileExistsError('Existing paired results are not overwritten.')
    record = read(directory / 'validation.json')
    pairs = []
    for task in record['tasks']:
        for repeat in range(1, record['repetitions'] + 1):
            selected = [job for job in record['jobs'] if job['task_index'] == task['task_index'] and job['repeat'] == repeat]
            sides = {job['version']: observed_side(job, record['libraries'][job['version']]) for job in selected}
            differences = {}
            for name in sides['parent']['metrics']:
                a, b = [sides[version]['metrics'][name] for version in VERSIONS]
                numeric = all(isinstance(value, (int, float)) and not isinstance(value, bool)
                              and math.isfinite(value) for value in [a, b])
                differences[name] = {'parent': a, 'candidate': b, 'candidate_minus_parent': b - a if numeric else None}
            pairs.append({'pair_id': selected[0]['pair_id'], 'task': task, 'repeat': repeat,
                          'execution_order': [job['version'] for job in selected],
                          'parent': sides['parent'], 'candidate': sides['candidate'], 'metric_differences': differences})
    comparison = {'schema_version': 1, 'kind': 'paired_candidate_validation',
        'validation_directory': str(directory), 'libraries': record['libraries'],
        'library_comparison': record['library_comparison'], 'candidate_source_record': record['candidate_source_record'],
        'context': record['context'],
        'student_budget': record['student_budget'], 'evaluation': record['evaluation'],
        'model': record['model'], 'reasoning_effort': record['reasoning_effort'],
        'coverage': {'planned_pairs': len(record['tasks']) * record['repetitions'],
                     'planned_attempts': len(record['jobs']),
                     'attempt_status_counts': dict(Counter(job['status'] for job in record['jobs']))},
        'pairs': pairs, 'execution_error': record.get('execution_error'),
        'data_policy': record['data_policy'], 'promotion_status': 'not_performed',
        'limits': ['All planned pairs and sides are retained, including unavailable libraries, unattempted runs, failures and missing evaluations.',
                   'Differences are candidate minus parent for existing observed metrics; missing or nonnumeric values have null differences. No composite score, ranking or significance claim.',
                   'SDK completion, file delivery, technical checks, automated RGB judgment and capability benefit are separate evidence.',
                   'Library byte changes do not prove a substantive improvement. Candidate reports are recorded claims, not validation results.',
                   'Original student/evaluator evidence is linked. Feedback paths grant no additional Improvement access without explicit evidence configuration.',
                   'No candidate repair, automatic promotion or next iteration is performed.']}
    write(directory / 'comparison.json', comparison)
    write(directory / 'feedback.json', dict(comparison, kind='paired_candidate_validation_feedback',
                                          comparison_record=str(directory / 'comparison.json')))
    record.update(status='collected', collected_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(directory / 'validation.json', record)
    return comparison


def run(directory):
    directory = Path(directory).resolve()
    record = read(directory / 'validation.json')
    if record['status'] != 'prepared' or (directory / 'feedback.json').exists():
        raise FileExistsError('Use a new prepared validation; existing attempts are not rerun.')
    record['status'] = 'started'
    write(directory / 'validation.json', record)
    try:
        for job in record['jobs']:
            if job['status'] != 'prepared':
                continue
            job['status'] = 'started'
            write(directory / 'validation.json', record)
            try:
                student.run(job['student_run'])
            except Exception as error:
                job['errors'].append({'stage': 'student', 'type': type(error).__name__, 'message': str(error)})
            try:
                output = evaluation.prepare(job['evaluation_input'])
                try:
                    evaluation.technical(output)
                    if read(output / 'evaluation.json')['visual']['status'] == 'prepared':
                        evaluation.visual(output)
                finally:
                    evaluation.collect(output)
            except Exception as error:
                job['errors'].append({'stage': 'evaluation', 'type': type(error).__name__, 'message': str(error)})
            job['status'] = 'finished_with_errors' if job['errors'] else 'finished'
            write(directory / 'validation.json', record)
    except BaseException as error:
        record['execution_error'] = {'type': type(error).__name__, 'message': str(error)}
        for job in record['jobs']:
            if job['status'] == 'started':
                job['status'] = 'interrupted'
        raise
    finally:
        write(directory / 'validation.json', record)
        collect(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'run', 'collect'])
    parser.add_argument('--input', type=Path)
    parser.add_argument('--directory', type=Path)
    args = parser.parse_args()
    if args.stage == 'prepare':
        if not args.input:
            parser.error('--input is required for prepare')
        print(prepare(args.input))
    else:
        if not args.directory:
            parser.error('--directory is required for run/collect')
        if args.stage == 'run':
            run(args.directory)
        else:
            collect(args.directory)


if __name__ == '__main__':
    main()
