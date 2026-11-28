"""Prepare and run one independent SDK student from an external reference and optional library."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import sys

from isolation import ROOT, prepare as prepare_isolated
from run_capability_acquisition import TOOLS, copy_tree, write, with_capability_library
from run_capability_improvement import RUNTIME_FILES
from run_sdk_session import execute

sys.path.insert(0, str(ROOT / 'analysis'))
from usage_summary import summarize


def prepare(input_file):
    input_file = Path(input_file).resolve()
    configuration = json.loads(input_file.read_text())

    def resolve(path):
        return (input_file.parent / path).resolve()

    directory = resolve(configuration['output_directory'])
    image = resolve(configuration['reference_image'])
    library = resolve(configuration['capability_library']) if configuration.get('capability_library') else None
    budget = configuration['budget']
    if library is not None and (directory == library or library in directory.parents):
        raise ValueError('The output directory must be outside the input capability library.')
    # The unchanged SDK sends its reference image as image/png.
    with image.open('rb') as reference:
        if reference.read(8) != b'\x89PNG\r\n\x1a\n':
            raise ValueError('Use a PNG reference image with the existing SDK image/png protocol.')
    directory.mkdir(parents=True)
    inputs = directory / 'inputs'
    inputs.mkdir()
    shutil.copy2(input_file, directory / 'input.json')
    shutil.copy2(image, inputs / 'reference.png')
    base = (ROOT / 'configs/formal_prompt.txt').read_text()
    (inputs / 'base_prompt.txt').write_text(base)
    if (budget['seconds'], budget['calls']) != (1500, 120):
        base = base.replace('The student time budget is 25 minutes, with at most 120 model requests.',
                            f"The student time budget is {budget['seconds']} seconds, with at most {budget['calls']} model requests.")
    if library is not None:
        copy_tree(library, directory / 'library')
    prompt = with_capability_library(base, directory / 'library' if library is not None else None)
    # Reuse the reviewed SDK source list; do not expose experimental source or library parents.
    for name in RUNTIME_FILES:
        if name.startswith('sdk/'):
            destination = directory / 'runtime' / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, destination)
    mounts = [{'source': str(directory / 'runtime/sdk'), 'target': '/sdk'}]
    if library is not None:
        mounts.append({'source': str(directory / 'library'), 'target': '/capabilities'})
    session = {'role': 'student', 'task_kind': 'independent_reconstruction', 'run_id': configuration['run_id'],
               'tools': TOOLS, 'readonly_mounts': mounts, 'hint_enabled': False,
               'persistent_capability_enabled': library is not None, 'online_teacher_enabled': False,
               'initial_images': [{'path': '/app/reference.png', 'label': 'Reference image'}]}
    prepare_isolated(directory, inputs / 'reference.png', prompt, session=session)
    invocation = {'directory': str(directory), 'image': str(inputs / 'reference.png'), 'prompt': prompt,
                  'seconds': budget['seconds'], 'calls': budget['calls'], 'cpus': budget['cpus'],
                  'port': budget['port'], 'session': session}
    write(inputs / 'invocation.json', invocation)
    files = [{'path': str(path.relative_to(directory / 'library')), 'bytes': path.stat().st_size}
             for path in sorted((directory / 'library').rglob('*')) if path.is_file()] if library else []
    record = {'run_id': configuration['run_id'], 'status': 'prepared',
              'prepared_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'source_configuration': str(input_file), 'reference_source': str(image),
              'library_source': str(library) if library else None,
              'runtime_library': str(directory / 'library') if library else None, 'library_files': files,
              'model': 'gpt-6.1-terra', 'reasoning_effort': 'low', 'execution_budget': budget,
              'independent_quality_evaluation': 'not_run', 'candidate_promotion': 'not_performed'}
    write(directory / 'run.json', record)
    return directory


def collect(directory):
    directory = Path(directory).resolve()
    if (directory / 'result.json').exists():
        raise FileExistsError('The existing student result is not overwritten.')
    record = json.loads((directory / 'run.json').read_text())
    state = json.loads((directory / 'status.json').read_text()) if (directory / 'status.json').exists() else None
    trajectory = directory / 'capture/trajs.json'
    sdk = json.loads(trajectory.read_text())['metadata'] if trajectory.exists() else {}
    files = [{'path': 'workspace/' + name, 'exists': (directory / 'workspace' / name).is_file(),
              'bytes': (directory / 'workspace' / name).stat().st_size if (directory / 'workspace' / name).is_file() else None}
             for name in ['build.py', 'scene.blend', 'final.png']]
    present = all(row['exists'] and row['bytes'] > 0 for row in files)
    write(directory / 'costs.json', summarize(directory, 'independent_student', root=directory.parent))
    result = {'run_id': record['run_id'], 'supervisor_state': state,
              'sdk_status': sdk.get('status', (state or {}).get('sdk_status')),
              'delivery': {'status': 'files_present_unvalidated' if present else 'missing_files',
                           'required_files_present': present, 'files': files,
                           'note': 'File presence is not scene validity, reproduction, or reconstruction quality.'},
              'costs': str(directory / 'costs.json'),
              'independent_quality_evaluation': 'not_run', 'candidate_promotion': 'not_performed'}
    if (directory / 'execution_error.json').exists():
        result['execution_error'] = json.loads((directory / 'execution_error.json').read_text())
    write(directory / 'result.json', result)
    record.update(status='collected', collected_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    write(directory / 'run.json', record)
    return result


def run(directory):
    directory = Path(directory).resolve()
    record = json.loads((directory / 'run.json').read_text())
    if record['status'] != 'prepared' or (directory / 'result.json').exists():
        raise FileExistsError('Use a newly prepared student run; existing attempts are not rerun.')
    record['status'] = 'started'
    write(directory / 'run.json', record)
    invocation = json.loads((directory / 'inputs/invocation.json').read_text())
    try:
        execute(**invocation)
    except BaseException as error:
        write(directory / 'execution_error.json', {'type': type(error).__name__, 'message': str(error)})
        raise
    finally:
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
