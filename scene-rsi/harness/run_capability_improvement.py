"""Feed recorded evaluations to one SDK teacher and preserve an unpromoted library candidate."""
import argparse
import datetime
import difflib
import errno
import json
import os
from pathlib import Path
import shutil
import sys

from run_capability_acquisition import TOOLS, copy_tree, write
from isolation import ROOT
from run_sdk_session import execute

sys.path.insert(0, str(ROOT / 'analysis'))
from usage_summary import summarize

EXCLUDED = {'.git', '.codex', '.agents', '.aws', '__pycache__', 'home', 'backend_home', 'tmp'}
RUNTIME_FILES = [
    'sdk/run_cc_sdk.py', 'sdk/codex_cli_bridge.py', 'sdk/codex_model_catalog.json',
    'sdk/logging_utils.py', 'sdk/skills_manager.py',
    'sdk/litellm_proxy/claude_code_proxy.py', 'sdk/litellm_proxy/streaming_fix.py',
    'harness/run_sdk_session.py', 'harness/isolation.py', 'harness/sdk_student.py',
    'harness/bridge_server.py', 'harness/proxy_server.py', 'harness/socket_tunnel.py',
    'harness/blender.py', 'configs/student_prompt.txt', 'configs/formal_prompt.txt',
    'configs/capability_improvement_prompt.txt',
]


def candidate_directory(path):
    directory = Path(path).resolve()
    if ROOT / 'experiments/capability_improvement' not in directory.parents:
        raise ValueError('Use a new attempt under experiments/capability_improvement; historical directories are not outputs.')
    return directory


def evidence_view(directory, sources, target, scope):
    """Expose only explicitly selected files; never follow evidence symlinks."""
    view = directory / target.lstrip('/')
    view.mkdir(parents=True)
    selections, files = [], []
    for number, source in enumerate(sources, 1):
        source = Path(source)
        if source.is_symlink():
            raise ValueError('Select the actual evidence path, not a symlink: ' + str(source))
        name = str(number).zfill(3) + '/' + source.name
        destination = view / name
        mounted = target + '/' + name
        selections.append({'source': str(source), 'path': mounted, 'scope': scope})
        paths = sorted(source.rglob('*')) if source.is_dir() else [source]
        for path in paths:
            relative = path.relative_to(source) if source.is_dir() else Path('.')
            if EXCLUDED.intersection(relative.parts) or path.name in {'auth.json', '.env'} or path.is_symlink():
                continue
            if path.is_dir():
                continue
            output = destination / relative if source.is_dir() else destination
            record = {'source': str(path), 'path': target + '/' + str(output.relative_to(view)),
                      'scope': scope, 'available': path.is_file()}
            if record['available']:
                output.parent.mkdir(parents=True, exist_ok=True)
                try:
                    os.link(path, output)
                except OSError as error:
                    if error.errno != errno.EXDEV:
                        raise
                    shutil.copy2(path, output)
                record['bytes'] = path.stat().st_size
            files.append(record)
    return selections, files


def prepare(directory, input_file):
    directory = candidate_directory(directory)
    input_file = Path(input_file).resolve()
    configuration = json.loads(input_file.read_text())

    def resolve(path):
        path = Path(path)
        return Path(os.path.abspath(input_file.parent / path))

    library = resolve(configuration['initial_library'])
    source_feedback = resolve(configuration['feedback'])
    budget = dict(configuration['budget'], model='gpt-6.1-terra', reasoning_effort='low')
    directory.mkdir(parents=True)
    copy_tree(library, directory / 'initial/library')
    copy_tree(library, directory / 'seed/library')
    # Keep the full source archive on the host. Only the reviewed runtime files
    # below are mounted; historical research source uses the explicit evidence input.
    for folder in ['sdk', 'harness', 'analysis']:
        copy_tree(ROOT / folder, directory / 'initial/system' / folder)
    for name in ['student_prompt.txt', 'formal_prompt.txt', 'capability_improvement_prompt.txt']:
        destination = directory / 'initial/system/configs' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / 'configs' / name, destination)
    for name in RUNTIME_FILES:
        destination = directory / 'runtime' / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, destination)
    (directory / 'inputs').mkdir()
    shutil.copy2(input_file, directory / 'inputs/input.json')
    shutil.copy2(source_feedback, directory / 'inputs/recorded_feedback.json')
    # Parse the real feedback now, before a model can be invoked.
    json.loads((directory / 'inputs/recorded_feedback.json').read_text())
    selected, files = {}, []
    mounts = [{'source': str(directory / folder), 'target': target}
              for folder, target in [('initial/library', '/initial/library'),
                                     ('runtime', '/initial/system'), ('runtime/sdk', '/sdk'),
                                     ('inputs', '/feedback')]]
    for key, target in [('evidence', '/evidence'), ('development_gt', '/development_gt'),
                        ('history', '/candidate_history')]:
        selected[key], rows = evidence_view(directory, [resolve(path) for path in configuration.get(key, [])], target, key)
        files += rows
        # Empty selections do not create GT/history mounts.
        if selected[key]:
            mounts.append({'source': str(directory / target.lstrip('/')), 'target': target})
    write(directory / 'inputs/evidence_index.json', {
        'selections': selected, 'files': files,
        'storage': 'Selected files only; read-only mounts. Hard links when on the same filesystem, copies otherwise.'})
    feedback = {
        'schema_version': 2,
        'purpose': 'One externally configured feedback-to-candidate attempt; not a formal experiment.',
        'execution_budget': budget,
        'recorded_feedback': '/feedback/recorded_feedback.json',
        'feedback_source': str(source_feedback),
        'components': {'initial_library': '/initial/library', 'writable_candidate': '/app/library',
                       'current_system_snapshot': '/initial/system', 'editable_scope': 'capability_library_only',
                       'runtime_source_files': RUNTIME_FILES,
                       'source_library': str(library)},
        'context': configuration.get('context', {}),
        'data_policy': {'used_outcomes': 'historical_development_experience',
                        'future_independent_test': 'Requires new held-out scenes not used for improvement.',
                        'access_scope': 'Only the selected input library, recorded feedback, common runtime source and explicitly listed evidence are available. Paths in records grant no access.',
                        'original_records_modified': False},
        'path_mapping': selected['evidence'] + selected['development_gt'] + selected['history'],
        'historical_container_paths': {'/app': '<selected historical session>/workspace',
                                       '/capture': '<selected historical session>/capture',
                                       '/capabilities': '<explicitly selected historical library, if supplied>',
                                       '/dev_gt': 'Use only allowed_development_gt below.'},
        'allowed_evidence': selected['evidence'],
        'allowed_development_gt': selected['development_gt'],
        'candidate_history': selected['history'],
        'evidence_index': '/feedback/evidence_index.json',
        'unavailable_evidence': [row['path'] for row in files if not row['available']],
    }
    write(directory / 'inputs/feedback.json', feedback)
    prompt = (ROOT / 'configs/capability_improvement_prompt.txt').read_text()
    (directory / 'inputs/prompt.txt').write_text(prompt)
    session = {'role': 'teacher', 'task_kind': 'capability_improvement',
               'tools': TOOLS, 'initial_images': [], 'readonly_mounts': mounts,
               'hint_enabled': False, 'persistent_capability_enabled': False}
    write(directory / 'inputs/session.json', session)
    invocation = {'directory': str(directory / 'session'), 'image': None,
                  'prompt': prompt, 'seconds': budget['seconds'], 'calls': budget['calls'],
                  'cpus': budget['cpus'], 'port': budget['port'],
                  'checkpoint': str(directory / 'seed'), 'session': session}
    write(directory / 'inputs/invocation.json', invocation)
    write(directory / 'candidate.json', {'status': 'prepared',
          'prepared_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'initial_library': str(directory / 'initial/library'), 'source_library': str(library),
          'host_system_archive': str(directory / 'initial/system'),
          'input_configuration': str(input_file), 'feedback': str(directory / 'inputs/feedback.json'),
          'agent_decision': None, 'independent_validation_status': 'not_run', 'promotion_status': 'not_promoted'})
    return feedback


def collect(directory):
    directory = candidate_directory(directory)
    output = directory / 'candidate'
    output.mkdir()
    workspace = directory / 'session/workspace'
    current = workspace / 'library'
    if current.exists():
        copy_tree(current, output / 'library')
    before = directory / 'initial/library'
    names = {str(path.relative_to(before)) for path in before.rglob('*') if path.is_file()}
    names |= {str(path.relative_to(current)) for path in current.rglob('*') if path.is_file()}
    changes, diff = [], []
    if workspace.exists():
        for name in sorted(names):
            old, new = before / name, current / name
            a = old.read_bytes() if old.is_file() else None
            b = new.read_bytes() if new.is_file() else None
            if a == b:
                continue
            changes.append({'path': name, 'kind': 'added' if a is None else 'removed' if b is None else 'modified'})
            diff.extend(difflib.unified_diff((a or b'').decode(errors='replace').splitlines(keepends=True),
                        (b or b'').decode(errors='replace').splitlines(keepends=True),
                        fromfile='initial/library/' + name, tofile='candidate/library/' + name))
    (output / 'library.diff').write_text(''.join(diff))
    write(output / 'file_changes.json', changes)
    report, report_status = None, 'missing'
    if (workspace / 'update_report.json').exists():
        shutil.copy2(workspace / 'update_report.json', output / 'update_report.json')
        try:
            report = json.loads((output / 'update_report.json').read_text())
            report_status = 'available' if isinstance(report, dict) else 'invalid_object'
        except json.JSONDecodeError:
            report_status = 'invalid_json'
    state = json.loads((directory / 'session/status.json').read_text()) if (directory / 'session/status.json').exists() else None
    costs = summarize(directory / 'session', 'development_candidate', root=directory)
    write(output / 'costs.json', costs)
    record = json.loads((directory / 'candidate.json').read_text())
    record.update(status='collected', session_state=state, report_status=report_status,
                  agent_decision=report.get('decision') if isinstance(report, dict) else None,
                  candidate_library=str(output / 'library') if current.exists() else None,
                  file_changes=changes, independent_validation_status='not_run', promotion_status='not_promoted',
                  next_validation_input=str(output / 'library') if current.exists() else None,
                  collected_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    if (directory / 'execution_error.json').exists():
        record['execution_error'] = json.loads((directory / 'execution_error.json').read_text())
    write(directory / 'candidate.json', record)
    return record


def run(directory):
    directory = candidate_directory(directory)
    if (directory / 'session').exists() or (directory / 'candidate').exists():
        raise FileExistsError('Use a new candidate directory; existing attempts are not overwritten.')
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
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--input', type=Path, help='External JSON input; relative paths are resolved beside this file.')
    args = parser.parse_args()
    if args.stage == 'prepare':
        if not args.input:
            parser.error('--input is required for prepare; use prepare_improvement_03a.py for the historical adapter')
        prepare(args.directory, args.input)
    elif args.stage == 'run':
        run(args.directory)
    else:
        collect(args.directory)


if __name__ == '__main__':
    main()
