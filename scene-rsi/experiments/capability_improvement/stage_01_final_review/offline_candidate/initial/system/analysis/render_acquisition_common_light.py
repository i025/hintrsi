"""Apply one posthoc white-world rendering condition to students and four GTs."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from evaluate_capability_acquisition import EXP, CPU_SETS, environment, blender, invoke, write


def render(template_run, source, output, identity, kind, lane, args):
    output.mkdir(parents=True)
    workspace = output / 'workspace_copy'
    shutil.copytree(source, workspace, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    argv = environment(template_run, output, workspace)
    # This renderer only needs its own copied scene, not student checkpoint evidence.
    index = 0
    while index < len(argv):
        if argv[index] in ('--bind', '--ro-bind') and argv[index + 2] == '/checkpoints':
            del argv[index:index + 3]
        else:
            index += 1
    execution = None
    if (workspace / 'scene.blend').exists():
        execution = invoke(blender(argv, '/analysis/acquisition_common_light.py',
                                   ['--input', '/app/scene.blend', '--output', '/capture/common_light.png',
                                    '--settings', '/capture/common_light_settings.json']),
                           output, 'render', CPU_SETS[lane], args.stage_seconds)
    image = output / 'capture/common_light.png'
    settings = output / 'capture/common_light_settings.json'
    result = {'id': identity, 'kind': kind, 'completed': True,
              'source_directory': str(source), 'source_blend': str(source / 'scene.blend'),
              'execution': execution, 'render_exists': image.exists(),
              'image': str(image) if image.exists() else None,
              'settings': str(settings) if settings.exists() else None,
              'status': ('missing_scene' if not (workspace / 'scene.blend').exists()
                         else 'rendered' if image.exists() and execution['exit_code'] == 0 else 'unavailable'),
              'cpu_set': CPU_SETS[lane], 'threads': 8, 'model_calls': 0,
              'student_action_credit': False, 'source_scene_saved_or_modified': False}
    write(output / 'result.json', result)
    print(kind, identity, result['status'], flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', type=Path, default=EXP)
    parser.add_argument('--workers', type=int, default=4, choices=(1, 2, 3, 4))
    parser.add_argument('--stage-seconds', type=int, default=600)
    args = parser.parse_args()
    args.experiment = args.experiment.resolve()
    runs = sorted((args.experiment / 'runs').iterdir())
    for run in runs:
        if (run / 'status.json').exists() and json.loads((run / 'status.json').read_text())['status'] in ('starting', 'running'):
            raise SystemExit('Student sessions are still active: ' + run.name)
    scenes = json.loads((args.experiment / 'configs/data_split.json').read_text())['test']
    tasks = [(run, run / 'workspace', run / 'analysis/technical/common_light', run.name, 'student') for run in runs]
    tasks += [(runs[0], Path(scene['directory']), args.experiment / 'data_preparation/new_scene_validation' / scene['id'] / 'common_light',
               scene['id'], 'ground_truth') for scene in scenes]
    def lane_work(lane):
        return [render(*task, lane, args) for task in tasks[lane::args.workers]]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(lane_work, lane) for lane in range(args.workers)]
        results = [row for future in futures for row in future.result()]
    write(args.experiment / 'analysis/common_light_index.json',
          {'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'complete': True,
           'student_count': len(runs), 'ground_truth_count': len(scenes), 'results': results,
           'rendered_count': sum(row['status'] == 'rendered' for row in results),
           'missing_scene_count': sum(row['status'] == 'missing_scene' for row in results),
           'render_failure_count': sum(row['status'] == 'unavailable' for row in results),
           'workers': args.workers, 'threads_each': 8, 'samples': 16,
           'model_calls': 0, 'condition': 'Uniform white world strength1, original light objects hidden; common CPU rendering and color management.',
           'interpretation': 'Evaluator-produced auxiliary appearance evidence; retained geometry, materials, emission and camera remain confounded. No full material-isolation or student-improvement claim.'})


if __name__ == '__main__':
    main()
