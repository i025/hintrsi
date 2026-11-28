"""External student inputs and recording contracts; no model requests."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import run_student as student
import run_capability_acquisition as acquisition

EXPERIMENT = ROOT / 'experiments/experiment_03a_capability_acquisition'
PREVIOUS = ROOT / 'experiments/capability_improvement/stage_01_verified_review/offline_candidate/candidate/library'
REFERENCE = Path(json.loads((ROOT / 'configs/scenes.json').read_text())['scenes'][0]['reference'])


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


class IndependentStudent(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='scene-student-test-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        root_patch = patch.object(student, 'ROOT', self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        for name in ['configs/formal_prompt.txt'] + [name for name in student.RUNTIME_FILES if name.startswith('sdk/')]:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        shutil.copytree(EXPERIMENT / 'libraries/A3', self.root / 'original')
        shutil.copytree(PREVIOUS, self.root / 'previous')
        shutil.copy2(REFERENCE, self.root / 'reference.png')

    def prepare(self, library='original', name='run', seconds=90, calls=3):
        input_file = self.root / (name + '.json')
        write(input_file, {'run_id': name, 'output_directory': name,
                          'reference_image': 'reference.png', 'capability_library': library,
                          'budget': {'seconds': seconds, 'calls': calls, 'cpus': [32, 33], 'port': 19665}})
        return student.prepare(input_file)

    def test_original_library_prompt_and_frozen_runtime_copy(self):
        directory = self.prepare()
        prompt = (directory / 'inputs/prompt.txt').read_text()
        self.assertIn((self.root / 'original/SKILL.md').read_text(), prompt)
        self.assertIn('90 seconds, with at most 3 model requests', prompt)
        self.assertNotIn('25 minutes', prompt)
        self.assertEqual(list((directory / 'workspace').iterdir()), [directory / 'workspace/reference.png'])
        before = (directory / 'library/SKILL.md').read_bytes()
        (self.root / 'original/SKILL.md').write_text('External source changed after prepare.\n')
        self.assertEqual((directory / 'library/SKILL.md').read_bytes(), before)
        invocation = json.loads((directory / 'inputs/invocation.json').read_text())
        self.assertEqual(invocation['seconds'], 90)
        self.assertEqual(invocation['calls'], 3)
        self.assertEqual(invocation['session']['tools'], acquisition.TOOLS)
        self.assertEqual(invocation['session']['readonly_mounts'][-1]['source'], str(directory / 'library'))
        self.assertNotIn('checkpoint', invocation)

    def test_candidate_is_used_directly_without_its_parent_evidence(self):
        directory = self.prepare('previous')
        self.assertTrue((directory / 'library/ENGINEERING_PROBE.md').exists())
        for path in (self.root / 'previous').iterdir():
            self.assertEqual(path.read_bytes(), (directory / 'library' / path.name).read_bytes())
        session = json.loads((directory / 'inputs/session.json').read_text())
        self.assertEqual([row['target'] for row in session['readonly_mounts']], ['/sdk', '/capabilities'])
        self.assertFalse(any((directory / name).exists() for name in ['evidence', 'development_gt', 'candidate_history']))

    def test_empty_library_prepares_an_original_student(self):
        directory = self.prepare(None, seconds=1500, calls=120)
        self.assertEqual((directory / 'inputs/prompt.txt').read_bytes(), (ROOT / 'configs/formal_prompt.txt').read_bytes())
        self.assertFalse((directory / 'library').exists())
        session = json.loads((directory / 'inputs/session.json').read_text())
        self.assertFalse(session['persistent_capability_enabled'])
        self.assertEqual([row['target'] for row in session['readonly_mounts']], ['/sdk'])

    def test_same_reference_with_three_independent_library_inputs(self):
        paths = [self.prepare(library, name) for library, name in [('original', 'a3'), ('previous', 'candidate'), (None, 'base')]]
        self.assertTrue(all((path / 'workspace/reference.png').read_bytes() == REFERENCE.read_bytes() for path in paths))
        self.assertEqual(len({path for path in paths}), 3)

    def test_non_png_reference_is_not_silently_sent_as_png(self):
        (self.root / 'reference.jpg').write_bytes(b'\xff\xd8Engineering non-PNG fixture.')
        input_file = self.root / 'jpeg.json'
        write(input_file, {'run_id': 'jpeg', 'output_directory': 'jpeg', 'reference_image': 'reference.jpg',
                          'budget': {'seconds': 90, 'calls': 3, 'cpus': [32, 33], 'port': 19665}})
        with self.assertRaisesRegex(ValueError, 'PNG reference'):
            student.prepare(input_file)
        self.assertFalse((self.root / 'jpeg').exists())

    def test_sdk_completion_and_delivery_are_separate(self):
        directory = self.prepare()
        def execute_fixture(**arguments):
            self.assertEqual(arguments['directory'], str(directory))
            self.assertEqual(arguments['session']['role'], 'student')
            self.assertEqual(arguments['session']['initial_images'], [{'path': '/app/reference.png', 'label': 'Reference image'}])
            write(directory / 'status.json', {'status': 'completed', 'sdk_status': 'completed'})
        with patch.object(student, 'execute', side_effect=execute_fixture) as execute:
            student.run(directory)
            execute.assert_called_once()
        result = json.loads((directory / 'result.json').read_text())
        self.assertEqual(result['sdk_status'], 'completed')
        self.assertEqual(result['delivery']['status'], 'missing_files')
        self.assertFalse(result['delivery']['required_files_present'])

    def test_files_present_do_not_imply_quality_validation_or_promotion(self):
        directory = self.prepare()
        for name in ['build.py', 'scene.blend', 'final.png']:
            (directory / 'workspace' / name).write_bytes(b'Engineering fixture, not a reconstruction.')
        result = student.collect(directory)
        self.assertEqual(result['delivery']['status'], 'files_present_unvalidated')
        self.assertIsNone(result['sdk_status'])
        self.assertEqual(result['independent_quality_evaluation'], 'not_run')
        self.assertEqual(result['candidate_promotion'], 'not_performed')

    def test_execution_failure_preserves_partial_files_and_costs(self):
        directory = self.prepare()
        def failed(**arguments):
            (directory / 'workspace/build.py').write_text('# Unfinished engineering fixture.\n')
            bridge = directory / 'bridge'
            bridge.mkdir()
            (bridge / 'model_requests.jsonl').write_text('{"request_id":"one"}\n{"request_id":"two"}\n')
            (bridge / 'token_usage.jsonl').write_text('{"request_id":"one","usage":{"input_tokens":100,"output_tokens":10,"cached_input_tokens":40}}\n')
            raise InterruptedError('Engineering fixture interruption')
        with patch.object(student, 'execute', side_effect=failed):
            with self.assertRaises(InterruptedError):
                student.run(directory)
        result = json.loads((directory / 'result.json').read_text())
        self.assertEqual(result['execution_error']['type'], 'InterruptedError')
        self.assertTrue((directory / 'workspace/build.py').exists())
        costs = json.loads((directory / 'costs.json').read_text())
        self.assertEqual(costs['requests'], 2)
        self.assertEqual(costs['requests_without_usage'], ['two'])
        self.assertEqual(costs['reported_tokens']['input_tokens'] + costs['reported_tokens']['output_tokens'], 110)

    def test_existing_directories_results_and_runs_are_not_overwritten(self):
        directory = self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        student.collect(directory)
        with self.assertRaises(FileExistsError):
            student.collect(directory)
        with patch.object(student, 'execute') as execute:
            with self.assertRaises(FileExistsError):
                student.run(directory)
            execute.assert_not_called()

    def test_output_cannot_be_created_inside_the_source_library(self):
        input_file = self.root / 'nested.json'
        write(input_file, {'run_id': 'nested', 'output_directory': 'original/nested',
                          'reference_image': 'reference.png', 'capability_library': 'original',
                          'budget': {'seconds': 90, 'calls': 3, 'cpus': [32, 33], 'port': 19665}})
        with self.assertRaisesRegex(ValueError, 'outside the input'):
            student.prepare(input_file)
        self.assertFalse((self.root / 'original/nested').exists())

    def test_original_03a_jobs_keep_exact_prompts_and_mounts(self):
        experiment = self.root / 'historical-03a'
        shutil.copytree(EXPERIMENT / 'libraries', experiment / 'libraries')
        (experiment / 'prompts').mkdir()
        shutil.copy2(ROOT / 'configs/formal_prompt.txt', experiment / 'prompts/base_student.txt')
        write(experiment / 'configs/data_split.json', {'test': [{'id': 'TEST', 'reference': str(REFERENCE)}]})
        with patch.object(acquisition, 'EXP', experiment):
            jobs = acquisition.student_jobs()
        self.assertEqual(len(jobs), 6)
        for job in jobs:
            group = job['id'].split('-')[-1]
            old_prompt = EXPERIMENT / 'prompts' / (group + '-student.txt')
            self.assertEqual(Path(job['prompt']).read_bytes(), old_prompt.read_bytes())
            session = json.loads(Path(job['session']).read_text())
            self.assertEqual(session['persistent_capability_enabled'], group != 'A0')
            self.assertEqual(session['readonly_mounts'], [] if group == 'A0' else [
                {'source': str(experiment / 'libraries' / group), 'target': '/capabilities'}])


if __name__ == '__main__':
    unittest.main()
