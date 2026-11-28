"""Fixed teacher hints and independent checkpoint branches through the existing SDK."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'experiments/experiment_01_natural_trajectories'
EXP = ROOT / 'experiments/experiment_02_teacher_guided_exploration'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
CASES = [('S01', 'S01-R1', 'Support and wheel/base connections of both office chairs'),
         ('S02', 'S02-R3', 'The bedroom door leaf orientation and foreground occlusion'),
         ('S03', 'S03-R2', 'The right kitchen countertop material and texture')]

BASE_PROMPT = '''Given the reference image and the provided reconstruction checkpoint, continue improving the editable Blender scene to reconstruct the reference as faithfully as possible, including visible objects, geometry, spatial relationships, materials, lighting, and camera viewpoint.

You start from the existing build.py, scene.blend, final.png, and local resources in /app. This is a new session with a shared scene checkpoint; the previous agent conversation has not been restored. Choose your own inspection, reconstruction, and revision workflow.

Use only the provided reference image, checkpoint, and available Blender environment. Do not retrieve an existing reconstruction or access external reference scene data.

Deliver executable Blender Python source with /app/build.py as its entry point, the editable /app/scene.blend, and /app/final.png at 640 x 360 pixels. Keep other required local source and material resources in /app. Rendering uses Blender 5.2.2 on CPU with eight threads. Your additional execution budget is 25 minutes and at most 120 model requests. You may finish early.
'''

GENERAL_CHECK = '''Carefully compare the reference image, current render, and existing scene. Identify and fix important discrepancies, and check whether your changes actually improve the reconstruction or introduce other problems.'''

TEACHER_PROMPT = '''You are a fixed candidate diagnostic teacher for an editable Blender reconstruction. You are not a human-aligned aesthetic teacher. Analyze only the provided RGB reference, current reconstruction, code, saved scene state, and observed SDK trajectory. Ground-truth Blender data and hidden reference geometry are not available and must not be inferred as known.

Inspect /app/build.py, /app/evidence/scene_state.json, /app/evidence/sdk_events.json, and /app/evidence/objective_evidence.json. The original SDK trajectory is also available at /app/evidence/original_trajectory.json. Read the images themselves. Distinguish observable defects, technical hypotheses, and competing explanations. Cite actual object names, code locations, or SDK event indices. Do not edit the reconstruction or supply final repair code, exact optimal coordinates, a complete solution, or claims about hidden reasoning.

Prepare guidance for the following single target: {target}.

Write /app/teacher_diagnosis.json as English JSON with these keys:
- target_defect: one precise, evidence-supported defect shared by every hint below.
- observations: an array of objects with claim and evidence fields.
- technical_hypotheses: an array with hypothesis, supporting_evidence, competing_explanation, and uncertainty fields.
- candidate_methods: at least two materially different methods, each with method, applicable_conditions, verification, and possible_side_effects.
- error_hint: a brief description of that defect only. Do not include a repair method, parameters, or code.
- strategy_extension: one targeted technical strategy for that SAME defect, including a verification direction. Do not give final code or exact repair parameters.
- exploration_extension: at least two materially different technical hypotheses or methods for that SAME defect. Ask the student to implement and compare candidates using evidence, and check side effects. Do not merely ask for more iterations. Do not give final code or exact repair parameters.
- knowledge_origin: what is already observable in the natural trajectory versus what is your own proposed technical prior.

The experiment will concatenate the identical error_hint with either extension, so do not change the target or repeat the entire task in the extensions. Keep the error hint under 100 words, strategy extension under 150 words, and exploration extension under 250 words. State unverified causes as hypotheses, not facts. Finish after writing the diagnosis; do not modify build.py, scene.blend, or final.png.
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def prepare():
    cases = []
    old_annotations = json.loads((OLD / 'analysis/annotations.json').read_text())
    separations = json.loads((OLD / 'analysis/support_separation.json').read_text())
    for scene, initial, target in CASES:
        run = OLD / 'runs' / initial
        checkpoint = EXP / 'checkpoints' / scene
        shutil.copytree(run / 'workspace', checkpoint, ignore=shutil.ignore_patterns('.git'))
        teacher = EXP / 'teacher_inputs' / scene
        shutil.copytree(checkpoint, teacher)
        evidence = teacher / 'evidence'
        evidence.mkdir()
        shutil.copyfile(run / 'analysis/technical/capture/final_state.json', evidence / 'scene_state.json')
        shutil.copyfile(run / 'analysis/sdk_events.json', evidence / 'sdk_events.json')
        shutil.copyfile(run / 'capture/trajs.json', evidence / 'original_trajectory.json')
        objective = {'source': initial, 'target': target,
                     'observations': [d for d in old_annotations['runs'][initial]['defects']],
                     'existing_separation_measurements': [d for d in separations if d['run'] == initial],
                     'scope': 'Existing reconstruction evidence only; no GT scene, coordinates, labels or hidden structure.'}
        write(evidence / 'objective_evidence.json', objective)
        prompt = EXP / 'prompts' / (scene + '-teacher.txt')
        prompt.parent.mkdir(exist_ok=True)
        prompt.write_text(TEACHER_PROMPT.format(target=target))
        session = EXP / 'configs' / (scene + '-teacher.json')
        write(session, {'role': 'teacher', 'tools': ['Read', 'Glob', 'Grep', 'Write'],
                        'hint_enabled': False, 'persistent_capability_enabled': False})
        cases.append({'scene': scene, 'source_run': initial, 'target': target,
                      'checkpoint': str(checkpoint), 'teacher_inputs': str(teacher),
                      'teacher_prompt': str(prompt), 'teacher_session': str(session),
                      'files': [{'path': str(p.relative_to(checkpoint)), 'bytes': p.stat().st_size}
                                for p in sorted(checkpoint.rglob('*')) if p.is_file()]})
    write(EXP / 'configs/cases.json', cases)
    (EXP / 'prompts/base_student.txt').write_text(BASE_PROMPT)
    print('Prepared three immutable case copies and teacher inputs.', flush=True)


def teacher_jobs():
    cases = json.loads((EXP / 'configs/cases.json').read_text())
    return [{'id': c['scene'], 'checkpoint': c['teacher_inputs'], 'prompt': c['teacher_prompt'],
             'session': c['teacher_session'], 'image': c['checkpoint'] + '/reference.png'} for c in cases]


def freeze():
    cases = json.loads((EXP / 'configs/cases.json').read_text())
    for case in cases:
        source = EXP / 'teachers' / case['scene'] / 'workspace/teacher_diagnosis.json'
        diagnosis = json.loads(source.read_text())
        hints = {'E0': '', 'E1': GENERAL_CHECK, 'E2': diagnosis['error_hint'],
                 'E3': diagnosis['error_hint'] + '\n\n' + diagnosis['strategy_extension'],
                 'E4': diagnosis['error_hint'] + '\n\n' + diagnosis['exploration_extension']}
        write(EXP / 'hints' / (case['scene'] + '.json'), {'diagnosis_source': str(source),
              'target': diagnosis['target_defect'], 'hints': hints,
              'word_counts': {key: len(value.split()) for key, value in hints.items()}})
        for condition, hint in hints.items():
            prompt = BASE_PROMPT + ('\nAdditional guidance:\n' + hint + '\n' if hint else '')
            (EXP / 'prompts' / (case['scene'] + '-' + condition + '.txt')).write_text(prompt)
            write(EXP / 'configs' / (case['scene'] + '-' + condition + '.json'),
                  {'role': 'student', 'condition': condition, 'hint_enabled': condition in ('E2', 'E3', 'E4'),
                   'generic_self_check': condition == 'E1', 'online_teacher_enabled': False,
                   'persistent_capability_enabled': False})
    # Balanced interleaving; each task receives each group once before repeats.
    order = [('S01', 'E2'), ('S02', 'E0'), ('S03', 'E4'), ('S01', 'E1'), ('S02', 'E3'),
             ('S03', 'E0'), ('S01', 'E4'), ('S02', 'E2'), ('S03', 'E1'), ('S01', 'E0'),
             ('S02', 'E4'), ('S03', 'E3'), ('S01', 'E3'), ('S02', 'E1'), ('S03', 'E2')]
    write(EXP / 'configs/frozen_design.json', {'frozen_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'model': 'gpt-6.1-terra', 'reasoning_effort': 'low', 'seconds': 1500, 'calls': 120,
          'workers': 2, 'threads': 8, 'cpu_sets': [list(range(32, 40)), list(range(40, 48))],
          'core_order': order, 'context': 'Fresh SDK session; identical checkpoint and two initial RGB images; no restored prior conversation.',
          'optional_extension': 'One complete independent repeat of all 15 branches in reversed order, if core completes within three hours and at least 150 minutes remain. No partial group-dependent extensions.',
          'second_checkpoint_or_E5': 'Not in this batch; prioritize complete repeats, independent evaluation and evidence analysis.',
          'gt_available_to_teacher_or_student': False, 'teacher_hint_updates_after_freeze': False,
          'numerical_tolerance_blender_units': 0.0001,
          'deadline_epoch': json.loads((EXP / 'start.json').read_text())['deadline_epoch']})
    print('Froze diagnoses, hints, prompts, and complete paired order.', flush=True)


def student_jobs(repetition):
    design = json.loads((EXP / 'configs/frozen_design.json').read_text())
    cases = {c['scene']: c for c in json.loads((EXP / 'configs/cases.json').read_text())}
    order = design['core_order'] if repetition == 1 else list(reversed(design['core_order']))
    return [{'id': s + '-' + e + '-R' + str(repetition), 'checkpoint': cases[s]['checkpoint'],
             'image': cases[s]['checkpoint'] + '/reference.png',
             'prompt': str(EXP / 'prompts' / (s + '-' + e + '.txt')),
             'session': str(EXP / 'configs' / (s + '-' + e + '.json'))} for s, e in order]


def batch(jobs, label, directory, seconds=1500, calls=120):
    queue = list(jobs)
    active, completed = {}, []
    started = time.time()
    deadline = json.loads((EXP / 'start.json').read_text())['deadline_epoch']
    stop = False

    def interrupt(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        while queue or active:
            for lane, (process, job, output) in list(active.items()):
                if process.poll() is not None:
                    completed.append({'run': job['id'], 'exit_code': process.returncode, 'finished_at': time.time()})
                    output.close()
                    del active[lane]
                    print(json.dumps(completed[-1]), flush=True)
            if (EXP / 'STOP').exists() or time.time() >= deadline - 3600:
                stop = True
            if stop:
                break
            for lane in range(2):
                if lane in active or not queue:
                    continue
                job = queue.pop(0)
                target = directory / job['id']
                target.mkdir(parents=True)
                argv = [PYTHON, '-u', '-B', str(ROOT / 'harness/run_sdk_session.py'),
                        '--directory', str(target), '--image', job['image'], '--prompt', job['prompt'],
                        '--checkpoint', job['checkpoint'], '--session-config', job['session'],
                        '--seconds', str(seconds), '--calls', str(calls), '--port', str(18965 + lane),
                        '--cpus', ','.join(str(cpu) for cpu in range(32 + lane * 8, 40 + lane * 8))]
                output = (target / 'supervisor.log').open('wb')
                process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                active[lane] = (process, job, output)
                print(json.dumps({'launched': job['id'], 'batch': label, 'lane': lane, 'timestamp': time.time()}), flush=True)
            write(EXP / (label + '_status.json'), {'started_at': started, 'updated_at': time.time(),
                  'active': [v[1]['id'] for v in active.values()], 'queued': [v['id'] for v in queue],
                  'completed': completed, 'concurrency': 2, 'seconds': seconds, 'calls': calls})
            time.sleep(2)
    finally:
        for process, _, _ in active.values():
            process.terminate()
        for process, _, output in active.values():
            process.wait()
            output.close()
        write(EXP / (label + '_finished.json'), {'started_at': started, 'finished_at': time.time(),
              'seconds': time.time() - started, 'completed': completed, 'unstarted': [v['id'] for v in queue],
              'interrupted': stop, 'owned_supervisors_stopped': True})


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'teachers', 'freeze', 'core', 'repeat'])
    args = parser.parse_args()
    if args.stage == 'prepare': prepare()
    elif args.stage == 'teachers': batch(teacher_jobs(), 'teachers', EXP / 'teachers', 900, 40)
    elif args.stage == 'freeze': freeze()
    else:
        repetition = 1 if args.stage == 'core' else 2
        batch(student_jobs(repetition), args.stage, EXP / 'runs')
