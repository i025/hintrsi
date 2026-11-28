"""Generic evaluation contracts, with no model calls or Blender reconstruction in unit tests."""
import importlib.util
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'analysis'), str(ROOT / 'harness')]
AVAILABLE = importlib.util.find_spec('numpy') is not None
if AVAILABLE:
    import evaluate_student as evaluation
    import run_capability_improvement as improvement

EXPERIMENT = ROOT / 'experiments/experiment_03a_capability_acquisition'
REFERENCE = Path(json.loads((ROOT / 'configs/scenes.json').read_text())['scenes'][0]['reference'])
PREVIOUS = ROOT / 'experiments/capability_improvement/stage_01_verified_review/offline_candidate/candidate/library'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


@unittest.skipUnless(AVAILABLE, 'Use the existing scenemosaic analysis environment for evaluation tests.')
class IndependentEvaluation(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='scene-evaluation-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.student = self.root / 'arbitrary.name-outside-experiment'
        (self.student / 'workspace').mkdir(parents=True)
        (self.student / 'inputs').mkdir()
        shutil.copy2(REFERENCE, self.student / 'inputs/reference.png')
        shutil.copy2(REFERENCE, self.student / 'workspace/reference.png')
        shutil.copy2(REFERENCE, self.student / 'workspace/final.png')
        (self.student / 'workspace/build.py').write_text('print("Engineering fixture only")\n')
        (self.student / 'workspace/scene.blend').write_bytes(b'Engineering fixture, not opened in unit tests.')
        shutil.copytree(EXPERIMENT / 'libraries/A3', self.student / 'library')
        (self.student / 'inputs/prompt.txt').write_text((self.student / 'library/SKILL.md').read_text())
        write(self.student / 'run.json', {'status': 'collected', 'run_id': 'external-id',
                                         'runtime_library': str(self.student / 'library')})
        write(self.student / 'status.json', {'status': 'completed', 'sdk_status': 'completed'})
        write(self.student / 'sdk_command.json', ['engineering-command-not-executed'])

    def prepare(self, name='evaluation', items=None):
        configuration = self.root / (name + '.json')
        write(configuration, {'student_run': self.student.name, 'output_directory': name,
              'items': items if items is not None else evaluation.ITEMS,
              'budget': {'cpus': [32, 33], 'stage_seconds': 30, 'visual_seconds': 40,
                         'visual_calls': 2, 'visual_port': 19865}})
        return evaluation.prepare(configuration)

    def test_arbitrary_name_uses_saved_reference_and_library_snapshot(self):
        (self.student / 'workspace/reference.png').write_bytes(b'Changed workspace copy')
        output = self.prepare()
        record = evaluation.read(output / 'evaluation.json')
        self.assertEqual(record['run_id'], 'external-id')
        self.assertEqual((output / 'reference.png').read_bytes(), REFERENCE.read_bytes())
        self.assertEqual(record['runtime_library'], str(self.student / 'library'))
        self.assertEqual(record['runtime_library_status'], 'snapshot_available')

    def test_original_candidate_and_empty_library_runs_can_be_prepared(self):
        self.prepare('original')
        shutil.rmtree(self.student / 'library')
        shutil.copytree(PREVIOUS, self.student / 'library')
        output = self.prepare('candidate')
        library = Path(evaluation.read(output / 'evaluation.json')['runtime_library'])
        self.assertTrue((library / 'ENGINEERING_PROBE.md').exists())
        shutil.rmtree(self.student / 'library')
        write(self.student / 'run.json', {'status': 'collected', 'runtime_library': None})
        output = self.prepare('base')
        self.assertEqual(evaluation.read(output / 'evaluation.json')['runtime_library_status'], 'none')

    def test_legacy_library_is_unknown_without_a_runtime_snapshot(self):
        shutil.rmtree(self.student / 'library')
        (self.student / 'run.json').unlink()
        write(self.student / 'status.json', {'status': 'completed', 'condition': 'A3',
                                            'persistent_capability_enabled': True})
        output = self.prepare(items=[])
        feedback = evaluation.collect(output)
        self.assertIsNone(feedback['inputs']['runtime_library'])
        self.assertEqual(feedback['inputs']['runtime_library_status'], 'unknown')

    def test_old_evidence_default_output_is_preserved(self):
        index = evaluation.summarize_evidence(self.student)
        self.assertEqual(index['run'], self.student.name)
        self.assertTrue((self.student / 'analysis/evidence_index.json').exists())

    def test_complete_partial_and_no_delivery_remain_separate_outcomes(self):
        for name, removed, expected in [('complete', [], 'complete_files_unvalidated'),
             ('partial', ['scene.blend'], 'partial'), ('none', ['build.py', 'final.png'], 'none')]:
            for path in removed:
                (self.student / 'workspace' / path).unlink()
            output = self.prepare(name)
            result = evaluation.collect(output)
            self.assertEqual(result['student']['delivery']['kind'], expected)
            self.assertIsNone(result['visual']['result'])
            self.assertEqual(result['technical']['reproduction']['status'], 'not_run')

    def test_technical_functions_are_reused_without_writing_student_analysis(self):
        output = self.prepare(items=['reproduction', 'images', 'evidence'])
        before = (self.student / 'workspace/build.py').read_bytes()
        with patch.object(evaluation.technical_checks, 'reproduce', return_value=(
                {'exit_code': 0, 'timeout': False, 'source_portable_deliverables': False}, output / 'replica')) as reproduce:
            results = evaluation.technical(output)
        reproduce.assert_called_once_with(self.student, output / 'technical/source_only', '32,33', 30)
        self.assertEqual(results['images']['status'], 'completed')
        self.assertEqual(results['evidence']['status'], 'completed')
        self.assertFalse((self.student / 'analysis').exists())
        self.assertEqual((self.student / 'workspace/build.py').read_bytes(), before)
        self.assertTrue((output / 'technical/evidence/code_facts.json').exists())

    def test_missing_code_does_not_skip_available_images_or_evidence(self):
        (self.student / 'workspace/build.py').unlink()
        (self.student / 'workspace/scene.blend').unlink()
        output = self.prepare()
        results = evaluation.technical(output)
        self.assertEqual(results['reproduction']['status'], 'skipped')
        self.assertEqual(results['scene']['status'], 'skipped')
        self.assertEqual(results['images']['status'], 'completed')
        self.assertEqual(results['evidence']['status'], 'completed')

    def test_visual_input_is_exact_existing_prompt_and_only_two_images(self):
        write(self.student / 'old_score.json', {'score': 'must not enter blind review'})
        output = self.prepare(items=['visual'])
        invocation = evaluation.read(output / 'visual/invocation.json')
        self.assertEqual(invocation['prompt'], evaluation.VISUAL_PROMPT)
        self.assertEqual(invocation['seconds'], 40)
        self.assertEqual(invocation['calls'], 2)
        self.assertEqual(invocation['session']['role'], 'visual_evaluator')
        self.assertEqual(invocation['session']['tools'], ['Read', 'Write'])
        self.assertNotIn('condition', invocation['session'])
        self.assertFalse(invocation['session']['persistent_capability_enabled'])
        self.assertEqual([row['target'] for row in invocation['session']['readonly_mounts']], ['/sdk'])
        self.assertEqual({p.name for p in (output / 'visual/session/workspace').iterdir()}, {'reference.png', 'final.png'})
        self.assertEqual({p.name for p in (output / 'visual/session/inputs').iterdir()}, {'prompt.txt', 'session.json', 'images.json'})
        self.assertNotIn((self.student / 'library/SKILL.md').read_text(), invocation['prompt'])

    def test_visual_dispatch_without_a_report_does_not_create_a_score(self):
        output = self.prepare(items=['visual'])
        with patch.object(evaluation, 'execute') as execute:
            evaluation.visual(output)
            execute.assert_called_once()
        result = evaluation.collect(output)
        self.assertEqual(result['visual']['status'], 'missing_or_invalid_report')
        self.assertIsNone(result['visual']['result'])
        self.assertIsNone(result['visual']['human_rating'])
        self.assertFalse(result['costs']['visual']['total_calls_known'])

    def test_invalid_visual_json_is_preserved_as_unknown(self):
        output = self.prepare(items=['visual'])
        def fixture(**invocation):
            (Path(invocation['directory']) / 'workspace/visual_evaluation.json').write_text('{invalid engineering fixture')
        with patch.object(evaluation, 'execute', side_effect=fixture):
            evaluation.visual(output)
        feedback = evaluation.collect(output)
        self.assertEqual(feedback['visual']['status'], 'invalid_json_report')
        self.assertIsNone(feedback['visual']['result'])
        self.assertEqual((output / 'visual/session/workspace/visual_evaluation.json').read_text(), '{invalid engineering fixture')

    def test_failed_reproduction_does_not_discard_other_checks(self):
        output = self.prepare(items=['reproduction', 'images'])
        with patch.object(evaluation.technical_checks, 'reproduce', side_effect=OSError('Engineering fixture execution error')):
            result = evaluation.technical(output)
        self.assertEqual(result['reproduction']['status'], 'failed')
        self.assertEqual(result['images']['status'], 'completed')

    def test_active_runs_and_existing_outputs_are_not_evaluated_or_overwritten(self):
        write(self.student / 'status.json', {'status': 'running'})
        with self.assertRaises(ValueError):
            self.prepare()
        write(self.student / 'status.json', {'status': 'completed'})
        output = self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        evaluation.collect(output)
        with self.assertRaises(FileExistsError):
            evaluation.collect(output)

    def test_feedback_is_accepted_by_existing_external_improvement_prepare(self):
        output = self.prepare(items=[])
        feedback = evaluation.collect(output)
        for folder in ['sdk', 'harness', 'analysis', 'configs']:
            shutil.copytree(ROOT / folder, self.root / folder)
        input_file = self.root / 'improvement_input.json'
        write(input_file, {'initial_library': str(self.student / 'library'), 'feedback': str(output / 'feedback.json'),
                          'evidence': [str(self.student / 'workspace')], 'development_gt': [], 'history': [],
                          'budget': {'seconds': 20, 'calls': 1, 'cpus': [32, 33], 'port': 19665}})
        candidate = self.root / 'experiments/capability_improvement/offline'
        with patch.object(improvement, 'ROOT', self.root):
            improvement.prepare(candidate, input_file)
        self.assertEqual(evaluation.read(candidate / 'inputs/recorded_feedback.json'), feedback)
        self.assertEqual(evaluation.read(candidate / 'inputs/feedback.json')['allowed_development_gt'], [])


if __name__ == '__main__':
    unittest.main()
