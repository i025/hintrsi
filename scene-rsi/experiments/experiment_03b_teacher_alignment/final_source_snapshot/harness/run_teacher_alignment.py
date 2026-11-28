"""Independent blinded perceptual critics through the existing SDK and Bridge."""
import argparse
import datetime
import json
from pathlib import Path
import random
import shutil
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'
OLD = ROOT / 'experiments/experiment_01_natural_trajectories'
PREVIOUS = ROOT / 'experiments/experiment_02_teacher_guided_exploration'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
ANALYSIS_PYTHON = '/srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python'

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


def research_summary():
    seed = EXP / 'research_inputs/research_reporter'
    seed.mkdir(parents=True)
    paired = json.loads((EXP / 'analysis/paired_predictions.json').read_text())
    fields = ('anonymous_id', 'split', 'reference_group', 'T0', 'T1', 'score_T1_minus_T0',
              'top_priority_categories', 'top_priority_category_changed', 'human_rating')
    write(seed / 'paired_predictions.json', [{key: row[key] for key in fields} for row in paired])
    index = []
    for row in paired:
        name = 'cases/' + row['anonymous_id'] + '.json'
        write(seed / name, {key: row[key] for key in fields})
        index.append({'anonymous_id': row['anonymous_id'], 'split': row['split'],
                      'reference_group': row['reference_group'], 'case_file': name})
    write(seed / 'case_index.json', index)
    for name in ('prediction_summary.json', 'usage_summary.json', 'request_audit.json', 'base_reproduction.json'):
        source = EXP / 'analysis' / name
        if source.exists(): shutil.copyfile(source, seed / name)
    for name in ('PROTOCOL.md', 'ENGINEERING_LOG.md', 'runtime_versions.json'):
        shutil.copyfile(EXP / name, seed / name)
    for name in ('module_interfaces.json', 'frozen_design.json', 'formal_runtime.json', 'independent_reference_scenes.json'):
        shutil.copyfile(EXP / 'configs' / name, seed / name)
    write(seed / 'human_interface_facts.json', {
          'genuine_human_annotations_received': False, 'human_ratings_all_null': True,
          'development_form': 'human_review/development/index.html',
          'independent_form': 'human_review/independent/index.html',
          'fields': ['coarse0-100 fidelity', 'up to3 prioritized visual defects', 'optional severity and text', 'same-reference pair preference'],
          'hidden': ['experimental group', 'teacher score', 'GT', 'automatic metrics', 'expected outcome'],
          'export': 'Separate development and independent human JSON; browser-local autosave; full form directory works offline.',
          'genuine_import': 'analysis/human_teacher_alignment.py import --input /absolute/path/to/export.json',
          'development_only_followup': 'analysis/human_teacher_alignment.py prepare-followup',
          'T2_T3_status': 'Interfaces only; no models run; require genuine development labels and a separate future selection split.',
          'source_boundary': 'No new Agent SDK. Perceptual critic derives from Experiment02 independent visual review but removes all predefined object/defect targets. Technical/exploration interfaces reuse Experiment02 TEACHER_PROMPT.',
          'publication_status': 'Local only; generate a GitHub synchronization index without uploading this batch.'})
    prompt = """You are the automated research reporter for Scene RSI Experiment03-B. Write a complete Chinese research report from the actual preserved evidence. All real research model sessions use Claude Agent SDK -> existing Codex CLI Bridge -> gpt-6.1-terra, low. You are not a human rater. The controller may verify paths and numeric facts but must not replace your scientific interpretation.

Read /app/case_index.json and all of its individual cases/*.json files, which hold the paired frozen T0/T1 judgments in manageable chunks. Do not mistake a truncated Read of the combined paired_predictions.json for reviewing all cases. Also read prediction_summary.json, usage_summary.json, request_audit.json, PROTOCOL.md, ENGINEERING_LOG.md, runtime_versions.json, module_interfaces.json, frozen_design.json, formal_runtime.json, independent_reference_scenes.json and human_interface_facts.json. If base_reproduction.json exists, use its actual technical checks. Do not read or infer genuine human labels: none have been received. Selection rationales, old defect targets, old automatic quality metrics and GT are intentionally not inputs to this comparison.

T0 is a generic independent RGB critic; T1 adds the user's provisional principle that relative positions, orientation, spatial relationships/proportions and materials/textures often matter more than very small support gaps in the few observed examples. This is not a formal human score, a universal weight, or an alignment-trained teacher. Each original critic received exactly the actual reference and one actual candidate image in a fresh SDK session. Their JSON estimates are not visual ground truth. This report receives frozen recorded judgments; do not create new pixel-level truth from prose. Compare actual priorities/categories/scores, include unchanged and conflicting examples, and cite exact case IDs and fields.

The intended material is12 development cases from three old references and four independent cases from two new references, two reconstructions each. Read actual completed counts. Repeated versions within a reference are correlated. Existing old scenes have been seen by the user and are development-only. New Base students received no learned libraries or teacher hints; references do not overlap03-A tests. All critic predictions are frozen before human feedback. T2/T3 and Technical Diagnostician/Exploration Teacher are interfaces only. Only Perceptual Critic T0/T1 actually runs here. GT assistance for future technical diagnosis is distinct from RGB-only human alignment.

Write /app/teacher_comparison.json as English JSON with annotation_kind=automated_research_analysis, what_T0_already_detected, T1_changes, shared_or_conflicting_diagnoses, development_observations, independent_observations, examples_requiring_human_adjudication, conclusions_supported_now, conclusions_not_supported, next_steps_after_genuine_human_feedback. Ground claims in case IDs and exact recorded fields.

Also write /app/REPORT_ZH.md as a self-contained Chinese research report with exact evidence links relative to the experiment root. Answer: what T0 could already discover; whether it autonomously named the broad kinds of defects the human emphasized (without pretending per-case human agreement is known); what T1's principle actually changed; how to use the anonymous human forms; what alignment stages have not run; and how genuine feedback would continue. Include frozen model/SDK/Bridge/tool/budget/resource settings, scene-level split, all actual failures/interruptions/engineering restarts and preserved costs, source reuse, image transport, independent Base technical completion, major limitations and known token/call/time counts. Do not claim better human alignment without human labels or interpret a higher automatic score as an improved reconstruction. Pixel-identical reproduction establishes delivery consistency, not semantic fidelity or3D correctness. Same base model across students, critics and this analysis creates correlated bias. Dollar billing is unknown; Ofox calls are zero. Cached input/reasoning output are subsets. Clearly say the supplied usage ledger precedes your own report session; the controller will append its final numeric ledger afterward.

Use links: predictions/{anonymous_id}-T0.json and -T1.json; analysis/paired_predictions.json; analysis/prediction_summary.json; analysis/usage_summary.json; analysis/request_audit.json; analysis/base_reproduction.json; configs/module_interfaces.json; ENGINEERING_LOG.md; PROTOCOL.md; runtime_versions.json; human_review/development/index.html; human_review/independent/index.html; pre_runtime_isolation_fix/README.md; source_origin.json; sync_manifest.json. Include actual image figures as ![caption](analysis/development_gallery.png) and ![caption](analysis/independent_gallery.png). These paths will exist at the final report root even if they are not in your current input directory. Do not invent links to unavailable artifacts.

Keep model instructions/evidence-comparison JSON in English; the human-facing report must be Chinese. Preserve uncertainty and inconvenient results. Do not alter frozen predictions. Only Read and Write are available. Save both files and finish within ten minutes and36 model requests.
"""
    prompt_path = EXP / 'prompts/research_reporter.txt'
    prompt_path.write_text(prompt)
    config = EXP / 'configs/research_reporter.json'
    write(config, {'role': 'research_reporter', 'tools': ['Read', 'Write'], 'initial_images': [],
                   'hint_enabled': False, 'persistent_capability_enabled': False})
    target = EXP / 'research_analyses/research_reporter'
    target.mkdir(parents=True)
    first = json.loads((EXP / 'configs/development_cases.json').read_text())[0]
    argv = [PYTHON, '-u', '-B', str(ROOT / 'harness/run_sdk_session.py'), '--directory', str(target),
            '--image', str(Path(first['seed']) / 'reference.png'), '--checkpoint', str(seed),
            '--prompt', str(prompt_path), '--session-config', str(config), '--seconds', '600', '--calls', '36',
            '--port', '19265', '--cpus', '48,49,50,51,52,53,54,55']
    print('Research reporter exit:', supervise(argv, target), flush=True)


def finish():
    run_base()
    prepare_independent(EXP / 'configs/independent_base_results.json')
    run('independent')
    freeze()
    stages = [('summarize_teacher_alignment.py', []), ('evaluate_teacher_alignment.py', []),
              ('make_teacher_alignment_review.py', []), ('report_teacher_alignment.py', ['figures']),
              ('report_teacher_alignment.py', ['index'])]
    for name, arguments in stages:
        print('Analysis stage:', name, arguments, flush=True)
        subprocess.run(['nice', '-n', '15', 'taskset', '-c', '48-55', ANALYSIS_PYTHON,
                        '-u', '-B', str(ROOT / 'analysis' / name), *arguments], check=True)
    research_summary()
    subprocess.run([ANALYSIS_PYTHON, '-u', '-B', str(ROOT / 'analysis/summarize_teacher_alignment.py')], check=True)
    subprocess.run([ANALYSIS_PYTHON, '-u', '-B', str(ROOT / 'analysis/report_teacher_alignment.py'), 'report'], check=True)
    with socket.socket() as probe:
        port_closed = probe.connect_ex(('127.0.0.1', 19265)) != 0
    auth_copies = list(EXP.glob('reviews/*/backend_home/auth.json'))
    auth_copies += list(EXP.glob('base_students/*/backend_home/auth.json'))
    auth_copies += list(EXP.glob('research_analyses/*/backend_home/auth.json'))
    auth_copies += list(EXP.glob('pre_runtime_isolation_fix/reviews/*/backend_home/auth.json'))
    write(EXP / 'completion.json', {'completed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'human_labels_received': False, 'T2_T3_executed': False,
          'bridge_port_closed': port_closed, 'copied_auth_remaining': len(auth_copies),
          'publication_status': 'local_only_sync_manifest_prepared'})
    subprocess.run([ANALYSIS_PYTHON, '-u', '-B', str(ROOT / 'analysis/report_teacher_alignment.py'), 'index'], check=True)
    print('03-B complete; original results and engineering costs preserved.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'prepare-independent', 'prepare-base', 'base', 'development', 'independent', 'freeze', 'research-summary', 'finish'])
    parser.add_argument('--manifest')
    args = parser.parse_args()
    if args.stage == 'prepare': prepare_development()
    elif args.stage == 'prepare-independent': prepare_independent(args.manifest)
    elif args.stage == 'prepare-base': prepare_base(args.manifest)
    elif args.stage == 'base': run_base()
    elif args.stage == 'research-summary': research_summary()
    elif args.stage == 'finish': finish()
    elif args.stage == 'freeze': freeze()
    else: run(args.stage)
