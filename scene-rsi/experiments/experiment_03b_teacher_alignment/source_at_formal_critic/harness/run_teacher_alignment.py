"""Independent blinded perceptual critics through the existing SDK and Bridge."""
import argparse
import datetime
import json
from pathlib import Path
import random
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'
OLD = ROOT / 'experiments/experiment_01_natural_trajectories'
PREVIOUS = ROOT / 'experiments/experiment_02_teacher_guided_exploration'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'

BASE_PROMPT = '''You are an independent automated perceptual critic of image-to-3D scene reconstruction. Compare the actual reference image with the actual reconstruction image. Evaluate fidelity to the reference rather than beauty. Discover the important visible defects yourself. You have no ground-truth scene, experimental group, earlier diagnosis, other candidates, or human ratings. Do not infer hidden geometry as an observed visual error.
'''

HUMAN_PRINCIPLE = '''An initial observation from one human reviewing a small set of related reconstructions is that relative object positions, object orientation, overall spatial relationships and proportions, and materials/textures often affect overall reconstruction fidelity more than very small support gaps. Treat this as a provisional attention principle, not a universal ordering or fixed numerical weight. Judge the actual visible evidence in each image; do not invent these defects or ignore clearly important geometry and support problems.
'''

OUTPUT_PROMPT = '''Write /app/perceptual_review.json as English JSON with these fields:
annotation_kind: "automated_model";
overall_fidelity_estimate: a coarse integer from 0 to 100, with 100 meaning faithful to the visible reference, not photorealism or attractiveness;
scene_summary: a short description;
overall_evidence: observable reasons for the estimate;
main_defects: an array of at most five important visible defects, each containing category (object_identification_omission, relative_position_layout, orientation, relative_proportion, geometry_parts_connections, material_texture, camera_composition, lighting_shadow, or other), affected_objects, description, reference_region and reconstruction_region (normalized [left, top, right, bottom], or null when a regional claim cannot be made), severity (low/medium/high), priority (1 is highest, use distinct integers), confidence (0 to 1), evidence, and uncertainty;
strengths: visible aspects recovered well;
uncertainty: limitations and competing explanations;
human_rating: null.

Use the provided images themselves. There are only two images: Reference image and Current reconstruction image. A score is an initial automated judgment, not human ground truth or a validated aggregate metric. State uncertainty instead of inventing evidence. Do not read unrelated files or propose Blender repair code. The writable workspace is /app. Save the JSON once and finish. Your time budget is five minutes with at most 24 model requests. Tools are Read and Write.
'''

# Researcher-selected development cases, fixed before any T0/T1 predictions.
DEVELOPMENT = [
    ('S01', 'exp01', 'S01-R1', 'Natural reconstruction after actual camera revision.'),
    ('S01', 'exp01', 'S01-R2', 'Natural one-pass reconstruction with different layout and framing.'),
    ('S01', 'exp02', 'S01-E0-R2', 'Unguided continuation with changed scene appearance and layout.'),
    ('S01', 'exp02', 'S01-E4-R1', 'Exploration branch with verified local chair changes.'),
    ('S02', 'exp01', 'S02-R1', 'Natural reconstruction with visible outside-room framing.'),
    ('S02', 'exp02', 'S02-E0-R1', 'Unguided continuation with camera and foreground changes.'),
    ('S02', 'exp02', 'S02-E2-R2', 'High door projection overlap accompanied by a doorway relation counterexample.'),
    ('S02', 'exp02', 'S02-E4-R2', 'Exploration branch retaining limited target recovery.'),
    ('S03', 'exp01', 'S03-R1', 'Natural procedural material implementation.'),
    ('S03', 'exp01', 'S03-R2', 'Natural geometric surface marks implementation.'),
    ('S03', 'exp02', 'S03-E2-R2', 'Material change with mixed or worse target evidence.'),
    ('S03', 'exp02', 'S03-E4-R1', 'Actual alternative material comparisons with limited visual improvement.'),
]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def supervise(argv, target):
    with (target / 'supervisor.log').open('wb') as output:
        process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                if (EXP / 'STOP').exists():
                    process.terminate()
                    process.wait()
                    raise InterruptedError('Controller requested a saved stop.')
                time.sleep(2)
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait()
        return process.returncode


def prepare_development():
    records = list(DEVELOPMENT)
    random.Random(2026112803).shuffle(records)
    rows = []
    for index, (scene, source, run, reason) in enumerate(records, 1):
        identifier = 'D' + str(index).zfill(3)
        origin = (OLD if source == 'exp01' else PREVIOUS) / 'runs' / run / 'workspace'
        seed = EXP / 'inputs' / identifier
        seed.mkdir(parents=True)
        for name in ('reference.png', 'final.png'):
            shutil.copyfile(origin / name, seed / name)
        rows.append({'anonymous_id': identifier, 'split': 'development', 'reference_group': scene,
                     'source_experiment': source, 'source_run': run, 'source_workspace': str(origin),
                     'selection_reason': reason, 'seed': str(seed)})
    write(EXP / 'configs/development_cases.json', rows)
    (EXP / 'prompts').mkdir(parents=True, exist_ok=True)
    for condition in ('T0', 'T1'):
        text = BASE_PROMPT + '\n' + (HUMAN_PRINCIPLE + '\n' if condition == 'T1' else '') + OUTPUT_PROMPT
        (EXP / 'prompts' / (condition + '.txt')).write_text(text)
    write(EXP / 'configs/session.json', {'role': 'perceptual_critic', 'tools': ['Read', 'Write'],
          'hint_enabled': False, 'persistent_capability_enabled': False})
    write(EXP / 'configs/frozen_design.json', {
        'frozen_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'model': 'gpt-6.1-terra', 'reasoning_effort': 'low', 'seconds': 300, 'calls': 24,
        'concurrency': 1, 'port': 19265, 'cpus': list(range(48, 56)),
        'development_cases': 12, 'planned_independent_reference_scenes': 2,
        'planned_independent_cases': 4, 'new_scene_source': 'Base Harness with no capability library, Hint or teacher.',
        'ordering': 'Fixed randomized development case order; T0/T1 order alternates by case position.',
        'images': 'Exactly reference and one anonymous candidate; both real image messages.',
        'information_hidden': ['source run', 'group', 'selection reason', 'GT', 'prior metric', 'teacher diagnosis', 'other reviews'],
        'human_ratings_received': False, 'T2_T3': 'Not run before genuine development human annotations.',
        'deadline_epoch': 1795860658})
    print('Fixed 12 development cases and both teacher prompts.', flush=True)


def prepare_independent(manifest):
    sources = json.loads(Path(manifest).read_text())
    rows = []
    for index, source in enumerate(sources, 1):
        identifier = 'I' + str(index).zfill(3)
        seed = EXP / 'inputs' / identifier
        seed.mkdir(parents=True)
        origin = Path(source['workspace'])
        for name in ('reference.png', 'final.png'):
            shutil.copyfile(origin / name, seed / name)
        rows.append({'anonymous_id': identifier, 'split': 'independent',
                     'reference_group': source['reference_group'], 'seed': str(seed),
                     'source_workspace': str(origin), 'source_run': source.get('run'),
                     'selection_reason': 'New reference scene, Base Harness reconstruction; independent of development feedback.'})
    write(EXP / 'configs/independent_cases.json', rows)
    print('Fixed independent scene cases before critic predictions.', flush=True)


def prepare_base(manifest):
    sources = json.loads(Path(manifest).read_text())
    write(EXP / 'configs/independent_reference_scenes.json', sources)
    shutil.copyfile(ROOT / 'configs/formal_prompt.txt', EXP / 'prompts/base_student.txt')
    write(EXP / 'configs/base_student.json', {'role': 'student', 'hint_enabled': False,
          'persistent_capability_enabled': False, 'online_teacher_enabled': False})
    write(EXP / 'configs/base_student_design.json', {
          'frozen_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'model': 'gpt-6.1-terra', 'reasoning_effort': 'low',
          'seconds': 1500, 'calls': 120, 'repetitions': 2, 'reference_scenes': sources,
          'capability_library': None, 'teacher': None, 'hint': None, 'fresh_workspace': True,
          'order': 'Repetition first, scene interleaved; no result-based filtering or resampling.'})


def run_base():
    sources = json.loads((EXP / 'configs/independent_reference_scenes.json').read_text())
    completed, manifest = [], []
    for repetition in (1, 2):
        for source in sources:
            identifier = source['reference_group'] + '-R' + str(repetition)
            target = EXP / 'base_students' / identifier
            if target.exists():
                raise RuntimeError('An earlier Base directory exists; do not silently resample it.')
            if time.time() >= json.loads((EXP / 'configs/frozen_design.json').read_text())['deadline_epoch'] - 5400:
                raise RuntimeError('Stop launching new reconstructions to retain evaluation and analysis time.')
            target.mkdir(parents=True)
            argv = [PYTHON, '-u', '-B', str(ROOT / 'harness/run_sdk_session.py'),
                    '--directory', str(target), '--image', source['reference_image'],
                    '--prompt', str(EXP / 'prompts/base_student.txt'),
                    '--session-config', str(EXP / 'configs/base_student.json'),
                    '--seconds', '1500', '--calls', '120', '--port', '19265',
                    '--cpus', '48,49,50,51,52,53,54,55']
            print(json.dumps({'launched_base': identifier, 'timestamp': time.time()}), flush=True)
            exit_code = supervise(argv, target)
            completed.append({'id': identifier, 'exit_code': exit_code, 'finished_at': time.time()})
            manifest.append({'reference_group': source['reference_group'], 'run': identifier,
                             'workspace': str(target / 'workspace')})
            write(EXP / 'base_students_status.json', {'completed': completed, 'total': len(sources) * 2})
            print(json.dumps(completed[-1]), flush=True)
    write(EXP / 'configs/independent_base_results.json', manifest)


def run(split):
    cases = json.loads((EXP / 'configs' / (split + '_cases.json')).read_text())
    completed = []
    started = time.time()
    for index, case in enumerate(cases):
        conditions = ('T0', 'T1') if index % 2 == 0 else ('T1', 'T0')
        for condition in conditions:
            identifier = case['anonymous_id'] + '-' + condition
            target = EXP / 'reviews' / identifier
            if target.exists():
                raise RuntimeError('An earlier case directory exists; preserve it and select the intended next stage explicitly.')
            if time.time() >= json.loads((EXP / 'configs/frozen_design.json').read_text())['deadline_epoch'] - 3600:
                raise RuntimeError('Analysis reserve reached; no further critic session will be started.')
            target.mkdir(parents=True)
            argv = [PYTHON, '-u', '-B', str(ROOT / 'harness/run_sdk_session.py'),
                    '--directory', str(target), '--image', str(Path(case['seed']) / 'reference.png'),
                    '--checkpoint', case['seed'], '--prompt', str(EXP / 'prompts' / (condition + '.txt')),
                    '--session-config', str(EXP / 'configs/session.json'), '--seconds', '300', '--calls', '24',
                    '--port', '19265', '--cpus', '48,49,50,51,52,53,54,55']
            write(EXP / (split + '_status.json'), {'started_at': started, 'updated_at': time.time(),
                  'active': identifier, 'completed': completed, 'total': len(cases) * 2})
            print(json.dumps({'launched': identifier, 'timestamp': time.time()}), flush=True)
            exit_code = supervise(argv, target)
            completed.append({'id': identifier, 'exit_code': exit_code, 'finished_at': time.time()})
            print(json.dumps(completed[-1]), flush=True)
    write(EXP / (split + '_status.json'), {'started_at': started, 'finished_at': time.time(),
          'active': None, 'completed': completed, 'total': len(cases) * 2})


def freeze():
    records = []
    for directory in sorted((EXP / 'reviews').glob('*')):
        path = directory / 'workspace/perceptual_review.json'
        status = json.loads((directory / 'status.json').read_text())
        if path.exists():
            output = json.loads(path.read_text())
            frozen = EXP / 'predictions' / (directory.name + '.json')
            frozen.parent.mkdir(parents=True, exist_ok=True)
            if frozen.exists():
                if json.loads(frozen.read_text()) != output:
                    raise RuntimeError('Previously frozen output differs; do not replace original predictions.')
            else:
                shutil.copyfile(path, frozen)
            records.append({'id': directory.name, 'status': status['status'], 'output': str(frozen.relative_to(EXP)),
                            'score': output.get('overall_fidelity_estimate'), 'bytes': frozen.stat().st_size})
        else:
            records.append({'id': directory.name, 'status': status['status'], 'output': None})
    write(EXP / 'predictions/freeze.json', {'frozen_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'human_annotations_used': False, 'records': records, 'policy': 'Initial predictions are preserved and never updated from later human feedback.'})
    print('Preserved original predictions:', len(records), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'prepare-independent', 'prepare-base', 'base', 'development', 'independent', 'freeze'])
    parser.add_argument('--manifest')
    args = parser.parse_args()
    if args.stage == 'prepare': prepare_development()
    elif args.stage == 'prepare-independent': prepare_independent(args.manifest)
    elif args.stage == 'prepare-base': prepare_base(args.manifest)
    elif args.stage == 'base': run_base()
    elif args.stage == 'freeze': freeze()
    else: run(args.stage)
