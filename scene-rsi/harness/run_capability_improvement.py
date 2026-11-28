"""Feed recorded evaluations to one SDK teacher and preserve an unpromoted library candidate."""
import argparse
import datetime
import difflib
import json
import os
from pathlib import Path
import shutil
import sys

from run_capability_acquisition import ROOT, EXP, TOOLS, copy_tree, write
from run_sdk_session import execute

sys.path.insert(0, str(ROOT / 'analysis'))
from usage_summary import summarize

EXCLUDED = {'.git', '.codex', '.agents', '.aws', '__pycache__', 'home', 'backend_home', 'tmp'}


def candidate_directory(path):
    directory = Path(path).resolve()
    if ROOT / 'experiments/capability_improvement' not in directory.parents:
        raise ValueError('Use a new attempt under experiments/capability_improvement; historical directories are not outputs.')
    return directory


def mounted(path):
    return '/evidence/' + str(path.relative_to(ROOT))


def evidence_view(directory, experiment):
    """Reuse the historical index without duplicating large scientific payloads."""
    index = json.loads((experiment / 'file_index.json').read_text())
    prefix = str(experiment.relative_to(ROOT)) + '/'
    rows = []
    paths = [ROOT / row['path'] for row in index['files'] if row['path'].startswith(prefix)]
    paths += [experiment / 'file_index.json', experiment / 'sync_manifest.json']
    for path in sorted(set(paths)):
        relative = path.relative_to(experiment)
        # Full former-test GT is not needed to expose its recorded evaluation.
        if relative.parts[0] == 'data_preparation' and relative.parts[1] != 'development_gt':
            continue
        if EXCLUDED.intersection(relative.parts) or path.name in {'auth.json', '.env'} or path.is_symlink():
            continue
        record = {'source': str(path), 'path': mounted(path), 'available': path.is_file()}
        if record['available']:
            target = directory / 'evidence' / path.relative_to(ROOT)
            target.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, target)
            record['bytes'] = path.stat().st_size
        rows.append(record)
    write(directory / 'inputs/evidence_index.json', {'source_index': str(experiment / 'file_index.json'),
          'host_root': str(ROOT), 'mounted_root': '/evidence', 'files': rows,
          'storage': 'Hard links on the project filesystem, mounted read-only; no payload download or model audit.'})
    return rows


def prepare(directory, condition, experiment=EXP, history=(), seconds=600, calls=24,
            cpus=None, port=19665):
    directory, experiment = candidate_directory(directory), Path(experiment).resolve()
    directory.mkdir(parents=True)
    library = experiment / 'libraries' / condition
    copy_tree(library, directory / 'initial/library')
    copy_tree(library, directory / 'seed/library')
    for folder in ['sdk', 'harness', 'analysis', 'configs']:
        copy_tree(ROOT / folder, directory / 'initial/system' / folder)
    (directory / 'inputs').mkdir()
    evidence = evidence_view(directory, experiment)
    split = json.loads((experiment / 'configs/data_split.json').read_text())
    frozen = json.loads((experiment / 'configs/frozen_libraries.json').read_text())
    source = next(row for row in frozen['libraries'] if row['condition'] == condition)
    outcomes = json.loads((experiment / 'analysis/observed_results.json').read_text())
    mounts = [{'source': str(directory / folder), 'target': target}
              for folder, target in [('initial', '/initial'), ('inputs', '/feedback'), ('evidence', '/evidence')]]
    gt = []
    for scene in split['development']:
        target = '/development_gt/' + scene['id']
        mounts.append({'source': scene['evaluation_directory'], 'target': target})
        gt.append({'scene': scene['id'], 'path': target, 'blend': target + '/scene.blend',
                   'source': scene['evaluation_directory'], 'license': scene['license']})
    historical = []
    for number, path in enumerate(history, 1):
        path = Path(path).resolve()
        target = '/candidate_history/H' + str(number).zfill(3)
        # Expose the previous result and input, not its runtime homes or duplicated evidence view.
        for name in ['candidate.json', 'candidate', 'initial', 'inputs', 'session/workspace',
                     'session/capture', 'session/bridge', 'session/proxy',
                     'session/status.json', 'session/resources.jsonl']:
            if (path / name).exists():
                mounts.append({'source': str(path / name), 'target': target + '/' + name})
        historical.append({'source': str(path), 'path': target,
                           'record': json.loads((path / 'candidate.json').read_text())})
    budget = {'seconds': seconds, 'model_requests': calls, 'cpus': cpus or list(range(32, 40)),
              'port': port, 'model': 'gpt-6.1-terra', 'reasoning_effort': 'low'}
    feedback = {
        'schema_version': 1, 'purpose': 'One development feedback-to-candidate attempt; not a formal experiment.',
        'condition': condition, 'execution_budget': budget,
        'path_mapping': {'host_root': str(ROOT), 'mounted_root': '/evidence',
                         'note': 'Rebase original host paths using this mapping; consult evidence_index.json for actual availability.'},
        'historical_container_paths': {'scope': 'Paths inside an earlier session, not this candidate workspace.',
                                        '/app': '<historical run>/workspace',
                                        '/capture': '<historical run>/capture',
                                        '/capabilities': mounted(experiment / 'libraries') + '/<historical condition>',
                                        '/dev_gt': 'Use only the current allowed_development_gt list.'},
        'data_policy': {'experiment03a_outcomes': 'historical_development_experience',
                        'former_test_scene_ids': [scene['id'] for scene in split['test']],
                        'future_independent_test': 'Requires new held-out scenes; no such test is configured or launched here.',
                        'historical_split': mounted(experiment / 'configs/data_split.json'),
                        'original_records_modified': False,
                        'gt_scope': 'Only the original development GT directories below are directly mounted. Historical evaluations may contain GT-derived observations.'},
        'components': {'initial_library': '/initial/library', 'writable_candidate': '/app/library',
                       'current_system_snapshot': '/initial/system', 'editable_scope': 'capability_library_only',
                       'source_record': source},
        'generation': {'input': mounted(experiment / 'learning_inputs' / condition),
                       'execution': mounted(experiment / 'learning' / condition),
                       'prompt': mounted(experiment / 'prompts' / (condition + '-learning.txt')),
                       'session': mounted(experiment / 'configs' / (condition + '-learning.json'))},
        'validation': {'execution': mounted(experiment / 'validation' / condition),
                       'report': mounted(experiment / 'validation' / condition / 'workspace/validation_report.json'),
                       'rejected_alternatives': 'See the actual validation report and generation workspace/research_evidence.json.'},
        'student_outcomes': outcomes,
        'student_runs': [{'run': row['run'], 'path': mounted(experiment / 'runs' / row['run']),
                          'trajectory': mounted(experiment / 'runs' / row['run'] / 'capture/trajs.json'),
                          'code_scene_and_render': mounted(experiment / 'runs' / row['run'] / 'workspace'),
                          'independent_evaluation': mounted(experiment / 'runs' / row['run'] / 'analysis')}
                         for row in outcomes['runs']],
        'independent_evaluation': {'results': mounted(experiment / 'analysis'),
                                   'reviewer_records': mounted(experiment / 'acquisition_reviews'),
                                   'scope': 'Recorded evaluations are evidence, not newly verified truth or human ratings.'},
        'costs': {'record': json.loads((experiment / 'analysis/final_usage_summary.json').read_text()),
                  'source': mounted(experiment / 'analysis/final_usage_summary.json'),
                  'raw_records': 'Each historical session includes bridge/model_requests.jsonl, token_usage.jsonl, resources.jsonl and status.json when available.'},
        'allowed_development_gt': gt, 'candidate_history': historical,
        'evidence_index': '/feedback/evidence_index.json',
        'unavailable_evidence': [row['path'] for row in evidence if not row['available']],
    }
    write(directory / 'inputs/feedback.json', feedback)
    prompt = (ROOT / 'configs/capability_improvement_prompt.txt').read_text()
    (directory / 'inputs/prompt.txt').write_text(prompt)
    session = {'role': 'teacher', 'task_kind': 'capability_improvement', 'condition': condition,
               'tools': TOOLS, 'initial_images': [], 'readonly_mounts': mounts,
               'hint_enabled': False, 'persistent_capability_enabled': False}
    write(directory / 'inputs/session.json', session)
    invocation = {'directory': str(directory / 'session'), 'image': split['development'][0]['reference'],
                  'prompt': prompt, 'seconds': seconds, 'calls': calls, 'cpus': budget['cpus'], 'port': port,
                  'checkpoint': str(directory / 'seed'), 'session': session}
    write(directory / 'inputs/invocation.json', invocation)
    write(directory / 'candidate.json', {'status': 'prepared', 'condition': condition,
          'prepared_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'initial_library': str(directory / 'initial/library'), 'source_library': str(library),
          'feedback': str(directory / 'inputs/feedback.json'), 'agent_decision': None,
          'independent_validation_status': 'not_run', 'promotion_status': 'not_promoted'})
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
    parser.add_argument('--experiment', type=Path, default=EXP)
    parser.add_argument('--condition', choices=['A1', 'A2', 'A3', 'A4', 'A5'])
    parser.add_argument('--history', type=Path, action='append', default=[])
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--calls', type=int, default=24)
    parser.add_argument('--port', type=int, default=19665)
    parser.add_argument('--cpus', default='32,33,34,35,36,37,38,39')
    args = parser.parse_args()
    if args.stage == 'prepare':
        if not args.condition:
            parser.error('--condition is required for prepare')
        prepare(args.directory, args.condition, args.experiment, args.history, args.seconds, args.calls,
                [int(cpu) for cpu in args.cpus.split(',')], args.port)
    elif args.stage == 'run':
        run(args.directory)
    else:
        collect(args.directory)


if __name__ == '__main__':
    main()
