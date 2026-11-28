"""Exercise real library/task preparation and paired collection with simulated execution only."""
import argparse
from collections import Counter
import datetime
import json
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'harness'), str(ROOT / 'analysis')]
import run_candidate_validation as validation
import run_capability_improvement as improvement
from run_capability_acquisition import write


def contents(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--candidate-output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True)
    started = time.monotonic()
    previous = ROOT / 'experiments/capability_improvement/stage_01_verified_review/offline_candidate'
    parent, candidate = previous / 'initial/library', previous / 'candidate/library'
    historical = ROOT / 'experiments/experiment_03a_capability_acquisition/runs/A-T01-A3'
    scenes = validation.read(ROOT / 'configs/scenes.json')['scenes'][:2]
    before = {str(path): contents(path) for path in [parent, candidate, historical]}
    reference_before = {row['reference']: Path(row['reference']).read_bytes() for row in scenes}
    input_file = output / 'input.json'
    write(input_file, {'parent_library': str(parent), 'candidate_library': str(candidate),
        'candidate_record': str(previous / 'candidate.json'), 'output_directory': str(output / 'paired'),
        'tasks': [{'id': 'external-' + str(index), 'reference_image': row['reference']}
                  for index, row in enumerate(scenes, 1)], 'repetitions': 2,
        'student_budget': {'seconds': 60, 'calls': 2, 'cpus': [32, 33], 'port': 19875},
        'evaluation': {'items': ['images', 'evidence', 'visual'], 'budget': {'cpus': [32, 33],
            'stage_seconds': 30, 'visual_seconds': 40, 'visual_calls': 2, 'visual_port': 19876}},
        'context': {'kind': 'offline_engineering_test', 'simulated_execution': True, 'not_research': True,
                    'candidate_provenance': 'A real saved engineering candidate containing ENGINEERING_PROBE.md, not a model-learned improvement.',
                    'artifact_provenance': str(historical / 'workspace'),
                    'artifacts_are_copied_not_generated': True, 'new_model_calls': 0,
                    'new_student_reconstructions': 0, 'blender_executions': 0}})
    directory = validation.prepare(input_file)
    dispatches = []

    def fake_student(**invocation):
        run = Path(invocation['directory'])
        identifier = run.name
        names = ['build.py', 'scene.blend', 'final.png']
        if '-R01-V2' in identifier:
            names = ['build.py', 'final.png']
        if '-R02-V1' in identifier:
            names = []
        if '-R02-V2' in identifier:
            names = ['build.py']
        for name in names:
            shutil.copy2(historical / 'workspace' / name, run / 'workspace' / name)
        write(run / 'status.json', {'status': 'offline_engineering_simulation',
              'sdk_status': 'incomplete' if '-R02-' in identifier else 'completed',
              'model_agent_started': False, 'model_calls': 0, 'artifacts_copied_not_generated': True})
        dispatches.append({'kind': 'simulated_student_backend', 'directory': str(run),
            'seconds': invocation['seconds'], 'calls': invocation['calls'], 'cpus': invocation['cpus'],
            'tools': invocation['session']['tools'], 'copied_historical_files': names,
            'new_model_calls': 0, 'new_blender_executions': 0})
        if '-R02-V2' in identifier:
            raise RuntimeError('Offline engineering interruption fixture, not a research observation.')

    def fake_visual(**invocation):
        run = Path(invocation['directory'])
        assert invocation['prompt'] == validation.evaluation.VISUAL_PROMPT
        assert invocation['session']['tools'] == ['Read', 'Write']
        assert sorted(path.name for path in (run / 'workspace').iterdir()) == ['final.png', 'reference.png']
        assert [row['label'] for row in invocation['session']['initial_images']] == ['Reference image', 'Candidate reconstruction']
        assert [row['target'] for row in invocation['session']['readonly_mounts']] == ['/sdk']
        write(run / 'status.json', {'status': 'offline_engineering_simulation', 'model_agent_started': False, 'model_calls': 0})
        dispatches.append({'kind': 'simulated_visual_backend_without_report', 'directory': str(run),
            'seconds': invocation['seconds'], 'calls': invocation['calls'], 'cpus': invocation['cpus'],
            'anonymous_image_count': 2, 'new_model_calls': 0})

    with patch.object(validation.student, 'execute', side_effect=fake_student) as student_calls, \
         patch.object(validation.evaluation, 'execute', side_effect=fake_visual) as visual_calls:
        validation.run(directory)
    result = validation.read(directory / 'feedback.json')
    assert result['coverage']['planned_pairs'] == 4 and result['coverage']['planned_attempts'] == 8
    deliveries = []
    for pair in result['pairs']:
        for name in validation.VERSIONS:
            side = pair[name]
            deliveries.append(side['evaluation_feedback']['student']['delivery']['kind'])
            assert side['evaluation_feedback']['visual']['result'] is None
            assert contents(Path(side['evidence']['runtime_library'])) == before[str(parent if name == 'parent' else candidate)]
        assert pair['metric_differences']['model_visual_estimate_0_100']['candidate_minus_parent'] is None
    assert deliveries.count('complete_files_unvalidated') == 2 and deliveries.count('partial') == 4 and deliveries.count('none') == 2
    assert student_calls.call_count == 8 and visual_calls.call_count == 4
    next_input = output / 'improvement_input.json'
    write(next_input, {'initial_library': str(directory / 'libraries/candidate'), 'feedback': str(directory / 'feedback.json'),
        'evidence': [str(directory / 'libraries'), str(directory / 'students/T001-R01-V1/capture'),
                     str(directory / 'evaluations/T001-R01-V1/technical')],
        'development_gt': [], 'history': [],
        'context': {'kind': 'offline_engineering_test', 'simulated_execution': True, 'not_research': True},
        'budget': {'seconds': 60, 'calls': 2, 'cpus': [32, 33], 'port': 19877}})
    prepared = args.candidate_output.resolve()
    improvement.prepare(prepared, next_input)
    assert (prepared / 'inputs/recorded_feedback.json').read_bytes() == (directory / 'feedback.json').read_bytes()
    assert not (prepared / 'session').exists() and not (prepared / 'candidate').exists()
    assert not validation.read(prepared / 'inputs/feedback.json')['allowed_development_gt']
    assert all(contents(Path(path)) == original for path, original in before.items())
    assert all(Path(path).read_bytes() == image for path, image in reference_before.items())
    write(output / 'dispatches.json', dispatches)
    write(output / 'verification.json', {'kind': 'offline_engineering_simulation_not_research',
        'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'seconds': time.monotonic() - started, 'paired_feedback': str(directory / 'feedback.json'),
        'planned_pairs_retained': 4, 'planned_attempts_retained': 8,
        'simulated_student_backend_calls': student_calls.call_count,
        'simulated_visual_backend_calls_without_report': visual_calls.call_count,
        'simulated_delivery_counts': dict(Counter(deliveries)),
        'original_libraries_historical_run_and_references_unchanged': True,
        'prepared_runtime_libraries_match_selected_sources': True,
        'blind_rgb_prompt_tools_and_images_checked': True,
        'improvement_prepared_only': str(prepared), 'feedback_copied_unchanged': True,
        'new_model_calls': 0, 'new_student_reconstructions': 0, 'blender_executions': 0,
        'limits': 'Copied historical files and simulated statuses test engineering contracts only. Image metrics describe these copied fixtures. No candidate benefit, visual judgment, SDK model roundtrip, source regeneration, ranking, promotion or iteration has been measured.'})
    print(json.dumps({'verification': str(output / 'verification.json'), 'new_model_calls': 0,
                      'new_student_reconstructions': 0, 'seconds': time.monotonic() - started}))


if __name__ == '__main__':
    main()
