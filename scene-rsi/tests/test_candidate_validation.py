"""Paired entry contracts using real input files and explicitly simulated execution."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'harness'), str(ROOT / 'analysis')]
AVAILABLE = importlib.util.find_spec('numpy') is not None
if AVAILABLE:
    import run_candidate_validation as validation
    import run_capability_improvement as improvement

OLD = ROOT / 'experiments/experiment_03a_capability_acquisition/runs/A-T01-A3'
LIBRARY = ROOT / 'experiments/experiment_03a_capability_acquisition/libraries/A3'
PREVIOUS = ROOT / 'experiments/capability_improvement/stage_01_verified_review/offline_candidate'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


def contents(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}


@unittest.skipUnless(AVAILABLE, 'Use the existing scenemosaic analysis environment.')
class CandidateValidation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='scene-paired-validation-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        shutil.copytree(LIBRARY, self.root / 'parent')
        shutil.copytree(PREVIOUS / 'candidate/library', self.root / 'candidate')
        shutil.copy2(OLD / 'workspace/reference.png', self.root / 'reference.png')
        self.configuration = {'parent_library': 'parent', 'candidate_library': 'candidate',
            'candidate_record': str(PREVIOUS / 'candidate.json'), 'output_directory': 'validation',
            'tasks': [{'id': 'arbitrary.task', 'reference_image': 'reference.png'}], 'repetitions': 2,
            'student_budget': {'seconds': 60, 'calls': 2, 'cpus': [32, 33], 'port': 19875},
            'evaluation': {'items': ['images', 'evidence', 'visual'],
                           'budget': {'cpus': [32, 33], 'stage_seconds': 30, 'visual_seconds': 40,
                                      'visual_calls': 2, 'visual_port': 19876}},
            'context': {'kind': 'offline_engineering_test', 'simulated_execution': True, 'not_research': True}}

    def prepare(self):
        path = self.root / 'input.json'
        write(path, self.configuration)
        return validation.prepare(path)

    def fake_student(self, **invocation):
        run = Path(invocation['directory'])
        identifier = run.name
        # These are copied historical artifacts, never newly generated scenes.
        names = ['build.py', 'scene.blend', 'final.png']
        if '-R01-V2' in identifier:
            names.remove('scene.blend')
        if '-R02-V1' in identifier:
            names = []
        if '-R02-V2' in identifier:
            names = ['build.py']
        for name in names:
            shutil.copy2(OLD / 'workspace' / name, run / 'workspace' / name)
        write(run / 'status.json', {'status': 'offline_engineering_test',
              'sdk_status': 'incomplete' if '-R02-' in identifier else 'completed',
              'model_agent_started': False, 'model_calls': 0, 'simulated_execution': True})
        if '-R02-V2' in identifier:
            raise RuntimeError('Simulated engineering interruption, not a student observation.')

    def fake_visual(self, **invocation):
        run = Path(invocation['directory'])
        write(run / 'status.json', {'status': 'offline_engineering_test', 'model_agent_started': False,
                                    'model_calls': 0, 'simulated_execution': True})
        # No model report or score is fabricated.

    def test_original_parent_and_saved_candidate_are_frozen_independently(self):
        before = {name: contents(self.root / name) for name in ['parent', 'candidate']}
        directory = self.prepare()
        record = validation.read(directory / 'validation.json')
        self.assertEqual(record['library_comparison']['status'], 'changed')
        self.assertEqual(record['library_comparison']['file_changes'], [{'path': 'ENGINEERING_PROBE.md', 'kind': 'added'}])
        self.assertEqual(record['candidate_source_record']['record']['agent_decision'], None)
        for name in ['parent', 'candidate']:
            self.assertEqual(contents(directory / 'libraries' / name), before[name])
            self.assertEqual(contents(self.root / name), before[name])

    def test_same_task_budgets_prompt_tools_and_repeat_mapping(self):
        self.configuration['tasks'].append({'id': 'second external ID', 'reference_image': 'reference.png'})
        self.configuration['evaluation']['items'] = validation.evaluation.ITEMS
        directory = self.prepare()
        record = validation.read(directory / 'validation.json')
        self.assertEqual(len(record['jobs']), 8)
        self.assertEqual([job['version'] for job in record['jobs']], ['parent', 'candidate', 'candidate', 'parent'] * 2)
        references = set()
        for job in record['jobs']:
            run = Path(job['student_run'])
            invocation = validation.read(run / 'inputs/invocation.json')
            configuration = validation.read(Path(job['evaluation_input']))
            self.assertEqual(validation.read(Path(job['student_input']))['budget'], self.configuration['student_budget'])
            self.assertEqual(configuration['budget'], self.configuration['evaluation']['budget'])
            self.assertEqual(configuration['items'], self.configuration['evaluation']['items'])
            self.assertEqual(invocation['session']['tools'], validation.student.TOOLS)
            self.assertFalse(invocation['session']['hint_enabled'])
            self.assertFalse(invocation['session']['online_teacher_enabled'])
            self.assertEqual((run / 'inputs/base_prompt.txt').read_bytes(), (ROOT / 'configs/formal_prompt.txt').read_bytes())
            self.assertEqual(contents(run / 'library'), contents(directory / 'libraries' / job['version']))
            self.assertEqual([row['target'] for row in invocation['session']['readonly_mounts']], ['/sdk', '/capabilities'])
            references.add((run / 'inputs/reference.png').read_bytes())
            self.assertEqual(job['task_id'], self.configuration['tasks'][job['task_index'] - 1]['id'])
        self.assertEqual(references, {(self.root / 'reference.png').read_bytes()})
        self.assertFalse((directory / 'evaluations').exists())  # Prepare must not execute or evaluate.

    def test_external_changes_do_not_change_prepared_snapshots(self):
        directory = self.prepare()
        before = contents(directory / 'libraries/candidate')
        (self.root / 'candidate/SKILL.md').write_text('Changed outside the prepared validation.\n')
        self.assertEqual(contents(directory / 'libraries/candidate'), before)
        for job in validation.read(directory / 'validation.json')['jobs']:
            if job['version'] == 'candidate':
                self.assertEqual(contents(Path(job['student_run']) / 'library'), before)

    def test_unchanged_and_insufficient_evidence_are_not_fabricated_updates(self):
        self.configuration['candidate_library'] = 'parent'
        report = self.root / 'candidate_record.json'
        write(report, {'agent_decision': 'insufficient_evidence', 'promotion_status': 'not_promoted'})
        self.configuration['candidate_record'] = str(report)
        directory = self.prepare()
        result = validation.collect(directory)
        self.assertEqual(result['library_comparison'], {'status': 'unchanged', 'file_changes': []})
        self.assertEqual(result['candidate_source_record']['record']['agent_decision'], 'insufficient_evidence')
        self.assertEqual(result['promotion_status'], 'not_performed')

    def test_missing_candidate_is_retained_and_never_treated_as_an_empty_library_student(self):
        self.configuration['candidate_library'] = 'not-generated/library'
        directory = self.prepare()
        with patch.object(validation.student, 'execute', side_effect=self.fake_student) as execute, \
             patch.object(validation.evaluation, 'execute', side_effect=self.fake_visual):
            validation.run(directory)
        self.assertEqual(execute.call_count, 2)
        self.assertTrue(all(call.kwargs['directory'].endswith('-V1') for call in execute.call_args_list))
        result = validation.read(directory / 'comparison.json')
        self.assertEqual(result['library_comparison']['status'], 'unknown')
        for pair in result['pairs']:
            candidate = pair['candidate']
            self.assertEqual(candidate['attempt']['status'], 'library_unavailable')
            self.assertIsNone(candidate['actual_student_record'])
            self.assertIsNone(candidate['evaluation_feedback'])
            self.assertFalse(Path(candidate['attempt']['student_run']).exists())
            configuration = validation.read(Path(candidate['attempt']['student_input']))
            self.assertIsNotNone(configuration['capability_library'])
            self.assertFalse(Path(configuration['capability_library']).exists())
            self.assertTrue(all(row['candidate_minus_parent'] is None for row in pair['metric_differences'].values()))

    def test_incompatible_library_prepare_failure_does_not_drop_planned_pairs(self):
        (self.root / 'candidate/SKILL.md').unlink()
        directory = self.prepare()
        result = validation.collect(directory)
        self.assertEqual(len(result['pairs']), 2)
        for pair in result['pairs']:
            self.assertEqual(pair['candidate']['attempt']['status'], 'preparation_failed')
            self.assertEqual(pair['candidate']['attempt']['errors'][0]['stage'], 'student_prepare')

    def test_run_delegates_to_existing_entries_and_retains_all_outcomes(self):
        directory = self.prepare()
        with patch.object(validation.student, 'execute', side_effect=self.fake_student) as students, \
             patch.object(validation.evaluation, 'execute', side_effect=self.fake_visual) as reviews:
            validation.run(directory)
        self.assertEqual(students.call_count, 4)
        self.assertEqual(reviews.call_count, 2)
        result = validation.read(directory / 'feedback.json')
        self.assertEqual(result['coverage']['planned_attempts'], 4)
        self.assertEqual(result['coverage']['planned_pairs'], 2)
        first, second = result['pairs']
        self.assertEqual(first['parent']['evaluation_feedback']['student']['delivery']['kind'], 'complete_files_unvalidated')
        self.assertEqual(first['candidate']['evaluation_feedback']['student']['delivery']['kind'], 'partial')
        self.assertEqual(second['parent']['evaluation_feedback']['student']['delivery']['kind'], 'none')
        self.assertEqual(second['candidate']['attempt']['status'], 'finished_with_errors')
        self.assertEqual(second['candidate']['evaluation_feedback']['student']['delivery']['kind'], 'partial')
        self.assertEqual(first['parent']['evaluation_feedback']['visual']['status'], 'missing_or_invalid_report')
        self.assertIsNone(first['metric_differences']['model_visual_estimate_0_100']['candidate_minus_parent'])
        self.assertEqual(first['metric_differences']['mae_rgb']['candidate_minus_parent'], 0)
        self.assertIsNone(second['metric_differences']['mae_rgb']['candidate_minus_parent'])
        self.assertEqual(result['context']['kind'], 'offline_engineering_test')
        self.assertIsNone(first['parent']['costs']['visual']['record']['actual_billing_usd'])

    def test_numeric_differences_keep_zero_and_missing_separate(self):
        directory = self.prepare()
        jobs = validation.read(directory / 'validation.json')['jobs']
        for job, value in zip(jobs[:2], [0, 12]):
            write(Path(job['evaluation_directory']) / 'feedback.json', {'costs': {}, 'visual': {
                'result': {'overall_fidelity_estimate_0_100': value, 'engineering_fixture_only': True}}})
        result = validation.collect(directory)
        first, second = result['pairs']
        self.assertEqual(first['metric_differences']['model_visual_estimate_0_100']['candidate_minus_parent'], 12)
        self.assertIsNone(second['metric_differences']['model_visual_estimate_0_100']['candidate_minus_parent'])

    def test_nonnumeric_visual_value_does_not_become_a_numeric_score(self):
        directory = self.prepare()
        jobs = validation.read(directory / 'validation.json')['jobs']
        for job, value in zip(jobs[:2], [False, 'unknown']):
            write(Path(job['evaluation_directory']) / 'feedback.json', {'costs': {}, 'visual': {
                'result': {'overall_fidelity_estimate_0_100': value, 'engineering_fixture_only': True}}})
        self.assertIsNone(validation.collect(directory)['pairs'][0]['metric_differences']['model_visual_estimate_0_100']['candidate_minus_parent'])

    def test_evaluation_exception_keeps_student_records_and_other_attempts(self):
        directory = self.prepare()
        with patch.object(validation.student, 'execute', side_effect=self.fake_student), \
             patch.object(validation.evaluation, 'prepare', side_effect=OSError('Simulated engineering evaluation failure')):
            validation.run(directory)
        result = validation.read(directory / 'comparison.json')
        for pair in result['pairs']:
            for name in validation.VERSIONS:
                side = pair[name]
                self.assertIsNotNone(side['student_result'])
                self.assertIsNone(side['evaluation_feedback'])
                self.assertEqual(side['attempt']['errors'][-1]['stage'], 'evaluation')

    def test_interruption_preserves_attempted_and_unattempted_sides_without_retry(self):
        directory = self.prepare()
        with patch.object(validation.student, 'execute', side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                validation.run(directory)
        record = validation.read(directory / 'comparison.json')
        self.assertEqual(record['coverage']['attempt_status_counts'], {'interrupted': 1, 'prepared': 3})
        self.assertEqual(len(record['pairs']), 2)

    def test_existing_sources_outputs_and_results_are_preserved(self):
        originals = {name: contents(self.root / name) for name in ['parent', 'candidate']}
        directory = self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        validation.collect(directory)
        with self.assertRaises(FileExistsError):
            validation.collect(directory)
        with patch.object(validation.student, 'run') as run:
            with self.assertRaises(FileExistsError):
                validation.run(directory)
            run.assert_not_called()
        self.assertEqual({name: contents(self.root / name) for name in originals}, originals)

    def test_paired_feedback_is_accepted_by_existing_improvement_prepare(self):
        directory = self.prepare()
        validation.collect(directory)
        for folder in ['sdk', 'harness', 'analysis', 'configs']:
            shutil.copytree(ROOT / folder, self.root / 'system' / folder)
        configuration = self.root / 'improvement.json'
        write(configuration, {'initial_library': str(directory / 'libraries/candidate'),
            'feedback': str(directory / 'feedback.json'), 'evidence': [str(directory / 'libraries')],
            'development_gt': [], 'history': [],
            'budget': {'seconds': 60, 'calls': 2, 'cpus': [32, 33], 'port': 19877}})
        candidate = self.root / 'system/experiments/capability_improvement/paired_feedback'
        with patch.object(improvement, 'ROOT', self.root / 'system'):
            improvement.prepare(candidate, configuration)
        self.assertEqual((candidate / 'inputs/recorded_feedback.json').read_bytes(), (directory / 'feedback.json').read_bytes())
        self.assertEqual(validation.read(candidate / 'inputs/feedback.json')['allowed_development_gt'], [])
        self.assertFalse((candidate / 'session').exists())


if __name__ == '__main__':
    unittest.main()
