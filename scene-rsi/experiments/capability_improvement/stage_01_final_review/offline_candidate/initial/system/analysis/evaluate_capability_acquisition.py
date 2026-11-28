"""Independent source-only regeneration and passive facts for Experiment 03-A."""
import argparse
import ast
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time

import numpy as np
from PIL import Image

from image_metrics import metrics

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03a_capability_acquisition'
CPU_SETS = ['32-39', '40-47', '64-71', '72-79']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def environment(run, output, workspace, retain_capabilities=False):
    for name in ('capture', 'home', 'tmp', 'inputs'):
        (output / name).mkdir(parents=True, exist_ok=True)
    argv = json.loads((run / 'sdk_command.json').read_text())
    mapped = {'/app': workspace, '/capture': output / 'capture',
              '/home/student': output / 'home', '/tmp': output / 'tmp', '/inputs': output / 'inputs'}
    index = 0
    while index < len(argv):
        if argv[index] in ('--bind', '--ro-bind'):
            target = argv[index + 2]
            if target == '/model/proxy.sock' or (target.startswith('/capabilities') and not retain_capabilities):
                del argv[index:index + 3]
                continue
            if target in mapped:
                argv[index + 1] = str(mapped[target])
            index += 3
        else:
            index += 1
    argv = argv[:argv.index('--')]
    return argv + ['--ro-bind', str(ROOT / 'analysis'), '/analysis',
                   '--ro-bind', str(run / 'capture'), '/checkpoints']


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (32 * 1024 ** 3, 32 * 1024 ** 3))


def invoke(argv, output, name, cpus, timeout):
    command = ['nice', '-n', '15', 'taskset', '-c', cpus, *argv]
    write(output / (name + '_command.json'), command)
    started = time.time()
    with (output / (name + '.log')).open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True, preexec_fn=limits)
        try:
            code = process.wait(timeout=timeout)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            code = process.wait()
            timed_out = True
    text = (output / (name + '.log')).read_text(errors='replace')
    result = {'exit_code': code, 'seconds': time.time() - started, 'timeout': timed_out,
              'python_traceback': 'Traceback (most recent call last)' in text,
              'log': str(output / (name + '.log'))}
    write(output / (name + '_result.json'), result)
    return result


def blender(argv, script, arguments=(), blend=None):
    command = argv + ['--', '/runtime/bin/blender', '--background', '--disable-autoexec', '--python-exit-code', '1']
    if blend:
        command.append(blend)
    command += ['--python', script]
    if arguments:
        command += ['--', *arguments]
    return command


def code_facts(run):
    records = []
    paths = sorted((run / 'workspace').rglob('*.py'))
    paths += sorted((run / 'capture').glob('blender_*/code/**/*.py'))
    for path in paths:
        text = path.read_text(errors='replace')
        row = {'path': str(path.relative_to(run)), 'bytes': path.stat().st_size,
               'phase': 'final_written_source' if run / 'workspace' in path.parents else 'captured_at_blender_execution',
               'capability_path_mentions': [{'line': n, 'text': line[:500]}
                                            for n, line in enumerate(text.splitlines(), 1)
                                            if '/capabilities' in line]}
        try:
            tree = ast.parse(text)
            row['functions'] = [node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
            row['imports'] = [ast.get_source_segment(text, node) for node in ast.walk(tree)
                               if isinstance(node, (ast.Import, ast.ImportFrom))]
            calls = Counter(ast.unparse(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call))
            row['static_call_sites'] = dict(calls)
            row['syntax_error'] = None
        except SyntaxError as error:
            row['syntax_error'] = str(error)
        records.append(row)
    return {'source_records': records,
            'limits': 'Static call sites are written syntax, not proof of actual runtime invocation, strategy adoption, or final retention. Captured source versions are evidence from actual Blender execution.'}


def compare_images(original, regenerated, reference):
    result = {'original_exists': original.exists(), 'regenerated_exists': regenerated.exists(),
              'reference_comparison': metrics(reference, original) if original.exists() else None,
              'regenerated_reference_comparison': metrics(reference, regenerated) if regenerated.exists() else None}
    if original.exists() and regenerated.exists():
        a, b = Image.open(original).convert('RGBA'), Image.open(regenerated).convert('RGBA')
        result.update({'original_resolution': list(a.size), 'regenerated_resolution': list(b.size),
                       'final_resolution_640x360': a.size == b.size == (640, 360),
                       'rgba_pixel_identical': a.size == b.size and bool(np.array_equal(np.asarray(a), np.asarray(b))),
                       'rgb_pixel_identical': a.size == b.size and bool(np.array_equal(np.asarray(a)[:, :, :3], np.asarray(b)[:, :, :3])),
                       'original_regenerated_auxiliary': metrics(original, regenerated)})
    result['limits'] = 'Pixel and SSIM comparisons are appearance auxiliaries, not semantic or 3D reconstruction quality scores.'
    return result


def reproduce(run, output, cpus, timeout, retain_capabilities=False):
    replica = output / 'replica'
    shutil.copytree(run / 'workspace', replica, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    removed = []
    for name in ('scene.blend', 'scene.blend1', 'scene.blend2', 'final.png'):
        path = replica / name
        if path.exists():
            removed.append(name)
            path.unlink()
    argv = environment(run, output, replica, retain_capabilities)
    result = invoke(blender(argv, '/app/build.py'), output, 'regeneration', cpus, timeout)
    result.update({'entrypoint_exists': (replica / 'build.py').exists(),
                   'regenerated_blend': (replica / 'scene.blend').exists(),
                   'regenerated_render': (replica / 'final.png').exists(),
                   'removed_preexisting_deliverables': removed,
                   'external_capability_library_available': retain_capabilities,
                   'source_only': not retain_capabilities,
                   'gt_available': False, 'controller_repair': False})
    if (replica / 'scene.blend').exists():
        extraction = invoke(blender(argv, '/analysis/acquisition_scene_metrics.py',
                                    ['--input', '/app/scene.blend', '--output', '/capture/regenerated']),
                            output, 'regenerated_scene_inspection', cpus, timeout)
        result['scene_inspection'] = extraction
        summary = output / 'capture/regenerated/summary.json'
        result['scene_facts'] = json.loads(summary.read_text()) if summary.exists() else None
    result['source_portable_deliverables'] = (not retain_capabilities and result['exit_code'] == 0
                                               and result['regenerated_blend'] and result['regenerated_render']
                                               and bool(result.get('scene_facts'))
                                               and not result['scene_facts']['missing_external_images'])
    write(output / 'reproduction.json', result)
    return result, replica


def evaluate(run, scene, lane, args):
    started = time.time()
    cpus = CPU_SETS[lane]
    output = run / 'analysis/technical'
    output.mkdir(parents=True)
    source_only, replica = reproduce(run, output / 'source_only', cpus, args.stage_seconds)
    original_copy = output / 'original_copy'
    shutil.copytree(run / 'workspace', original_copy, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    inspection = output / 'original_inspection'
    argv = environment(run, inspection, original_copy)
    original = {'blend_exists': (original_copy / 'scene.blend').exists()}
    if original['blend_exists']:
        original['inspection'] = invoke(blender(argv, '/analysis/acquisition_scene_metrics.py',
                                                 ['--input', '/app/scene.blend', '--output', '/capture/original']),
                                         inspection, 'scene_inspection', cpus, args.stage_seconds)
        summary = inspection / 'capture/original/summary.json'
        original['scene_facts'] = json.loads(summary.read_text()) if summary.exists() else None
        if not args.no_extra_views:
            original['extra_views'] = invoke(blender(argv, '/analysis/extra_views.py', blend='/app/scene.blend'),
                                             inspection, 'extra_views', cpus, args.stage_seconds)
    checkpoints = []
    for path in sorted((run / 'capture').glob('blender_*/artifacts/**/*.blend*')):
        relative = path.relative_to(run / 'capture')
        checkpoints.append({'input': '/checkpoints/' + str(relative),
                             'output': '/capture/checkpoint_states/' + str(relative) + '.json'})
    write(inspection / 'inputs/states.json', checkpoints)
    checkpoint_result = invoke(blender(argv, '/analysis/extract_checkpoints.py'),
                               inspection, 'checkpoint_extraction', cpus, args.stage_seconds) if checkpoints else None
    images = compare_images(run / 'workspace/final.png', replica / 'final.png', Path(scene['reference']))
    write(output / 'image_comparison.json', images)
    write(output / 'method_facts.json', code_facts(run))
    same_condition = None
    if args.same_condition:
        same_condition, same_replica = reproduce(run, output / 'same_condition', cpus, args.stage_seconds, True)
        write(output / 'same_condition/image_comparison.json',
              compare_images(run / 'workspace/final.png', same_replica / 'final.png', Path(scene['reference'])))
    result = {'run': run.name, 'scene_id': scene['id'], 'group': run.name.rsplit('-', 1)[-1],
              'reference': scene['reference'], 'source_only_reproduction': source_only,
              'same_condition_auxiliary_reproduction': same_condition,
              'original': original, 'image_comparison': images,
              'checkpoint_count': len(checkpoints), 'checkpoint_extraction': checkpoint_result,
              'gt_instance_statistics': str(args.experiment / 'data_preparation/new_scene_validation' / scene['id'] / 'reference_instance_statistics.json'),
              'cpu_set': cpus, 'seconds': time.time() - started,
              'evaluation_scope': 'After all students end; no model calls, GT access in reproduction, feedback, repair, or inferred semantic/3D alignment.'}
    write(output / 'result.json', result)
    print(run.name, 'evaluated', round(result['seconds'], 2), 'seconds', flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', type=Path, default=EXP)
    parser.add_argument('--run', action='append')
    parser.add_argument('--workers', type=int, default=4, choices=(1, 2, 3, 4))
    parser.add_argument('--stage-seconds', type=int, default=600)
    parser.add_argument('--no-extra-views', action='store_true')
    parser.add_argument('--same-condition', action='store_true')
    args = parser.parse_args()
    args.experiment = args.experiment.resolve()
    started = time.time()
    all_runs = sorted((args.experiment / 'runs').iterdir())
    for run in all_runs:
        if (run / 'status.json').exists():
            status = json.loads((run / 'status.json').read_text())['status']
            if status in ('starting', 'running'):
                raise SystemExit('Student sessions are still active: ' + run.name)
    scenes = {row['id']: row for row in json.loads((args.experiment / 'configs/data_split.json').read_text())['test']}
    runs = [args.experiment / 'runs' / name for name in args.run] if args.run else all_runs
    def lane_work(lane):
        return [evaluate(run, scenes[run.name.rsplit('-', 1)[0]], lane, args)
                for run in runs[lane::args.workers]]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(lane_work, lane) for lane in range(args.workers)]
        results = [row for future in futures for row in future.result()]
    available = [json.loads((run / 'analysis/technical/result.json').read_text())
                 for run in all_runs if (run / 'analysis/technical/result.json').exists()]
    write(args.experiment / 'analysis/technical_summary.json', available)
    write(args.experiment / 'analysis/technical_evaluation_finished.json',
          {'finished_at_utc': datetime.now(timezone.utc).isoformat(), 'seconds': time.time() - started,
           'run_count': len(available), 'evaluated_now': len(results),
           'workers': args.workers, 'threads_each': 8,
           'cpu_sets': CPU_SETS[:args.workers], 'stage_timeout_seconds': args.stage_seconds,
           'source_only_is_primary': True, 'same_condition_auxiliary': args.same_condition,
           'model_calls': 0, 'student_code_modified': False,
           'source_reuse': ['evaluate_exploration.py: isolated regeneration and capture protocol',
                            'inspect_scene.py: original state schema',
                            'inspect_gt_03.py: detailed actual data inspection',
                            'extract_checkpoints.py: saved-state extraction',
                            'extra_views.py: posthoc camera perturbations',
                            'image_metrics.py: auxiliary image comparisons']})


if __name__ == '__main__':
    main()
