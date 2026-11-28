"""Reuse independent source regeneration for the new Base-only human cases."""
import json
from pathlib import Path
import shutil
import time

from evaluate_capability_acquisition import reproduce, compare_images, environment, invoke, blender
from evaluate_exploration import archive_temporary

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    runs = sorted((EXP / 'base_students').glob('*'))
    if any(json.loads((run / 'status.json').read_text())['status'] in ('starting', 'running') for run in runs):
        raise RuntimeError('Technical evaluation starts only after all Base student executions have ended.')
    results = []
    for run in runs:
        started = time.time()
        archive_temporary(run)
        output = run / 'analysis/technical'
        output.mkdir(parents=True)
        result, replica = reproduce(run, output / 'source_only', '48-55', 300)
        images = compare_images(run / 'workspace/final.png', replica / 'final.png', run / 'workspace/reference.png')
        original_copy = output / 'original_copy'
        shutil.copytree(run / 'workspace', original_copy, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
        inspection = output / 'original_inspection'
        argv = environment(run, inspection, original_copy)
        original = invoke(blender(argv, '/analysis/acquisition_scene_metrics.py',
                                  ['--input', '/app/scene.blend', '--output', '/capture/original']),
                          inspection, 'scene_inspection', '48-55', 300)
        facts = inspection / 'capture/original/summary.json'
        record = {'run': run.name, 'regeneration': result, 'images': images,
                  'original_scene_open': original,
                  'original_scene_facts': json.loads(facts.read_text()) if facts.exists() else None,
                  'seconds': time.time() - started, 'gt_provided': False,
                  'scope': 'Independent technical delivery check only; no controller scene repair or feedback to students/critics.'}
        write(output / 'result.json', record)
        results.append(record)
        write(EXP / 'analysis/base_reproduction.json', results)
        print(run.name, 'portable', result['source_portable_deliverables'], 'RGBA identical', images.get('rgba_pixel_identical'), flush=True)


if __name__ == '__main__': main()
