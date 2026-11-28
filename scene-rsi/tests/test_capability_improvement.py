"""Feedback/candidate contracts; no model backend or student experiment is started."""
import json
import errno
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'harness'))
import run_capability_improvement as improvement
from prepare_improvement_03a import configuration
from isolation import prepare as prepare_isolated

REAL = ROOT / 'experiments/experiment_03a_capability_acquisition'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2))


class FeedbackCandidates(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='scene-feedback-test-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.experiment = self.root / 'experiments/experiment_03a_capability_acquisition'
        self.candidate = self.root / 'experiments/capability_improvement/C001'
        self.root_patch = patch.object(improvement, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)
        for folder in ['sdk', 'harness', 'analysis', 'configs']:
            (self.root / folder).mkdir()
            (self.root / folder / 'source.txt').write_text('Engineering fixture only.\n')
        for name in ['student_prompt.txt', 'formal_prompt.txt', 'capability_improvement_prompt.txt']:
            shutil.copy2(ROOT / 'configs' / name, self.root / 'configs' / name)
        shutil.copytree(REAL / 'libraries/A3', self.experiment / 'libraries/A3')
        frozen = json.loads((REAL / 'configs/frozen_libraries.json').read_text())
        write(self.experiment / 'configs/frozen_libraries.json', frozen)
        development = self.root / 'development/S01'
        development.mkdir(parents=True)
        (development / 'scene.blend').write_bytes(b'engineering fixture, not a real scene')
        (development / 'reference.png').write_bytes(b'not used as a model image')
        split = {'development': [{'id': 'S01', 'evaluation_directory': str(development),
                 'reference': str(development / 'reference.png'), 'license': 'CC-BY-4.0'}],
                 'test': [{'id': 'A-T01'}]}
        write(self.experiment / 'configs/data_split.json', split)
        observed = json.loads((REAL / 'analysis/observed_results.json').read_text())
        self.outcome = next(row for row in observed['runs'] if row['run'] == 'A-T01-A2')
        write(self.experiment / 'analysis/observed_results.json', {'runs': [self.outcome], 'scope': observed['scope']})
        write(self.experiment / 'analysis/final_usage_summary.json', json.loads((REAL / 'analysis/final_usage_summary.json').read_text()))
        trajectory = self.experiment / 'runs/A-T01-A2/capture/trajs.json'
        trajectory.parent.mkdir(parents=True)
        shutil.copy2(REAL / 'runs/A-T01-A2/capture/trajs.json', trajectory)
        # The index deliberately includes a private runtime file to check exclusion.
        write(self.experiment / 'runs/A-T01-A2/backend_home/auth.json', {'fixture': True})
        files = [{'path': str(path.relative_to(self.root)), 'bytes': path.stat().st_size}
                 for path in self.experiment.rglob('*') if path.is_file()]
        write(self.experiment / 'file_index.json', {'files': files})
        write(self.experiment / 'sync_manifest.json', {'fixture': True})

    def prepare(self, directory=None, history=(), library=None, evidence=None, gt=()):
        directory = directory or self.candidate
        selected = [self.experiment / 'runs/A-T01-A2'] if evidence is None else evidence
        config = configuration('A3', self.experiment, evidence=selected, development_gt=gt,
                               history=history, seconds=90, calls=3, cpus=[32, 33], port=19665)
        if library:
            config['initial_library'] = str(library)
        input_file = self.root / (directory.name + '-input.json')
        write(input_file, config)
        return improvement.prepare(directory, input_file)

    def workspace(self):
        target = self.candidate / 'session/workspace'
        shutil.copytree(self.candidate / 'seed', target)
        return target

    def test_actual_outcome_and_original_trajectory_are_available(self):
        feedback = self.prepare()
        observed = json.loads((self.candidate / 'inputs/recorded_feedback.json').read_text())
        self.assertEqual(observed['runs'][0], self.outcome)
        self.assertFalse(observed['runs'][0]['complete_delivery'])
        self.assertIsNone(observed['runs'][0]['human_rating'])
        raw = self.candidate / 'evidence/001/A-T01-A2/capture/trajs.json'
        self.assertEqual(raw.read_bytes(), (REAL / 'runs/A-T01-A2/capture/trajs.json').read_bytes())
        self.assertFalse((raw.parent.parent / 'backend_home/auth.json').exists())

    def test_reclassification_is_a_new_record_not_an_edit_to_original_split(self):
        original = (self.experiment / 'configs/data_split.json').read_bytes()
        feedback = self.prepare()
        self.assertEqual(feedback['context']['outcomes_used_for_improvement'], 'historical_development_experience')
        self.assertIn('new held-out', feedback['data_policy']['future_independent_test'])
        self.assertEqual((self.experiment / 'configs/data_split.json').read_bytes(), original)
        self.assertEqual(feedback['allowed_development_gt'], [])

    def test_candidate_copy_and_diff_do_not_modify_original_library(self):
        self.prepare()
        original = (self.experiment / 'libraries/A3/SKILL.md').read_bytes()
        workspace = self.workspace()
        with (workspace / 'library/SKILL.md').open('a') as stream:
            stream.write('\nEngineering test marker.\n')
        (workspace / 'library/support.py').unlink()
        (workspace / 'library/engineering.md').write_text('Test marker only.\n')
        write(workspace / 'update_report.json', {'decision': 'candidate_update', 'changes': [], 'further_validation': ['not executed']})
        record = improvement.collect(self.candidate)
        self.assertEqual((self.experiment / 'libraries/A3/SKILL.md').read_bytes(), original)
        self.assertEqual((self.candidate / 'initial/library/SKILL.md').read_bytes(), original)
        kinds = {row['path']: row['kind'] for row in record['file_changes']}
        self.assertEqual(kinds, {'SKILL.md': 'modified', 'support.py': 'removed', 'engineering.md': 'added'})
        self.assertIn('Engineering test marker', (self.candidate / 'candidate/library.diff').read_text())
        self.assertEqual(record['promotion_status'], 'not_promoted')
        self.assertEqual(record['independent_validation_status'], 'not_run')

    def test_no_change_and_insufficient_evidence_are_valid_outcomes(self):
        for decision in ['no_change', 'insufficient_evidence']:
            with self.subTest(decision=decision):
                candidate = self.root / 'experiments/capability_improvement' / decision
                self.prepare(candidate)
                workspace = candidate / 'session/workspace'
                shutil.copytree(candidate / 'seed', workspace)
                write(workspace / 'update_report.json', {'decision': decision})
                record = improvement.collect(candidate)
                self.assertEqual(record['agent_decision'], decision)
                self.assertEqual(record['file_changes'], [])
                self.assertEqual(record['promotion_status'], 'not_promoted')

    def test_existing_sdk_execute_receives_recorded_input_and_budget(self):
        self.prepare()
        def sdk_fixture(**arguments):
            self.assertEqual(arguments['calls'], 3)
            self.assertEqual(arguments['seconds'], 90)
            self.assertEqual(arguments['cpus'], [32, 33])
            self.assertEqual(arguments['session']['role'], 'teacher')
            self.assertEqual(arguments['session']['initial_images'], [])
            self.assertIsNone(arguments['image'])
            self.assertNotIn('condition', arguments['session'])
            self.assertIn('/feedback/feedback.json', arguments['prompt'])
            self.assertEqual(arguments['checkpoint'], str(self.candidate / 'seed'))
            workspace = self.workspace()
            (workspace / 'library/sdk_fixture.md').write_text('Mock execution, not a model improvement.\n')
            write(workspace / 'update_report.json', {'decision': 'candidate_update'})
        with patch.object(improvement, 'execute', side_effect=sdk_fixture) as execute:
            improvement.run(self.candidate)
            execute.assert_called_once()
        self.assertTrue((self.candidate / 'candidate/library/sdk_fixture.md').exists())

    def test_interruption_preserves_candidate_without_claiming_success(self):
        self.prepare()
        def interrupted(**arguments):
            workspace = self.workspace()
            (workspace / 'library/progress.md').write_text('Unfinished engineering fixture.\n')
            write(self.candidate / 'session/status.json', {'status': 'engineering_failure'})
            raise InterruptedError('Engineering interruption fixture')
        with patch.object(improvement, 'execute', side_effect=interrupted):
            with self.assertRaises(InterruptedError):
                improvement.run(self.candidate)
        record = json.loads((self.candidate / 'candidate.json').read_text())
        self.assertEqual(record['session_state']['status'], 'engineering_failure')
        self.assertEqual(record['execution_error']['type'], 'InterruptedError')
        self.assertEqual(record['report_status'], 'missing')
        self.assertIsNone(record['agent_decision'])
        self.assertTrue((self.candidate / 'candidate/library/progress.md').exists())

    def test_invalid_report_is_retained_without_fabricating_a_decision(self):
        self.prepare()
        (self.workspace() / 'update_report.json').write_text('{not valid json')
        record = improvement.collect(self.candidate)
        self.assertEqual(record['report_status'], 'invalid_json')
        self.assertIsNone(record['agent_decision'])
        self.assertEqual((self.candidate / 'candidate/update_report.json').read_text(), '{not valid json')

    def test_existing_attempt_cannot_be_overwritten_or_reexecuted(self):
        self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare()
        self.workspace()
        with patch.object(improvement, 'execute') as execute:
            with self.assertRaises(FileExistsError):
                improvement.run(self.candidate)
            execute.assert_not_called()

    def test_history_contains_actual_record_and_no_runtime_home_mount(self):
        self.prepare()
        workspace = self.workspace()
        write(workspace / 'update_report.json', {'decision': 'no_change', 'rejected_candidates': ['fixture only']})
        improvement.collect(self.candidate)
        next_candidate = self.root / 'experiments/capability_improvement/C002'
        feedback = self.prepare(next_candidate, history=[self.candidate / 'candidate.json'])
        previous = feedback['candidate_history'][0]
        self.assertEqual(previous['path'], '/candidate_history/001/candidate.json')
        record = json.loads((next_candidate / 'candidate_history/001/candidate.json').read_text())
        self.assertEqual(record['agent_decision'], 'no_change')
        self.assertEqual(list((next_candidate / 'candidate_history').rglob('SKILL.md')), [])
        self.assertFalse((next_candidate / 'candidate_history/001/inputs').exists())

    def test_missing_usage_stays_unknown_and_cached_tokens_are_not_added_twice(self):
        self.prepare()
        self.workspace()
        bridge = self.candidate / 'session/bridge'
        bridge.mkdir()
        (bridge / 'model_requests.jsonl').write_text('{"request_id":"one"}\n{"request_id":"two"}\n')
        (bridge / 'token_usage.jsonl').write_text(json.dumps({'request_id': 'one', 'usage': {'input_tokens': 100, 'output_tokens': 10, 'cached_input_tokens': 40}})+'\n')
        improvement.collect(self.candidate)
        costs = json.loads((self.candidate / 'candidate/costs.json').read_text())
        self.assertEqual(costs['requests'], 2)
        self.assertEqual(costs['requests_without_usage'], ['two'])
        self.assertEqual(costs['reported_tokens']['input_tokens'] + costs['reported_tokens']['output_tokens'], 110)
        self.assertIsNone(costs['actual_billing_usd'])

    def test_startup_failure_is_preserved_even_before_workspace_exists(self):
        self.prepare()
        with patch.object(improvement, 'execute', side_effect=RuntimeError('Startup engineering fixture')):
            with self.assertRaises(RuntimeError):
                improvement.run(self.candidate)
        record = json.loads((self.candidate / 'candidate.json').read_text())
        self.assertEqual(record['execution_error']['message'], 'Startup engineering fixture')
        self.assertIsNone(record['candidate_library'])
        self.assertEqual(record['file_changes'], [])
        self.assertEqual(record['promotion_status'], 'not_promoted')

    def test_usage_summary_default_still_accepts_original_experiment_runs(self):
        record = improvement.summarize(REAL / 'runs/A-T01-A2', 'historical')
        self.assertEqual(record['directory'], 'experiments/experiment_03a_capability_acquisition/runs/A-T01-A2')
        self.assertEqual(record['requests'], 1)

    def test_all_entrypoints_reject_historical_directories_as_outputs(self):
        target = self.experiment / 'libraries/A3/forbidden_candidate'
        for function in [lambda: self.prepare(target), lambda: improvement.run(target),
                         lambda: improvement.collect(target)]:
            with self.assertRaises(ValueError):
                function()
        self.assertFalse(target.exists())

    def test_file_replaced_by_directory_keeps_the_actual_diff(self):
        self.prepare()
        workspace = self.workspace()
        entry = workspace / 'library/SKILL.md'
        entry.unlink()
        entry.mkdir()
        (entry / 'engineering.txt').write_text('Invalid library layout, engineering fixture only.\n')
        record = improvement.collect(self.candidate)
        changes = {row['path']: row['kind'] for row in record['file_changes']}
        self.assertEqual(changes, {'SKILL.md': 'removed', 'SKILL.md/engineering.txt': 'added'})
        self.assertEqual(record['promotion_status'], 'not_promoted')

    def test_same_library_with_different_evidence_and_optional_gt(self):
        first = self.prepare(evidence=[])
        other = self.root / 'experiments/capability_improvement/expanded'
        second = self.prepare(other, gt=[self.root / 'development/S01'])
        self.assertEqual(first['components']['source_library'], second['components']['source_library'])
        self.assertEqual(first['allowed_evidence'], [])
        self.assertEqual(len(second['allowed_evidence']), 1)
        self.assertEqual(first['allowed_development_gt'], [])
        self.assertEqual(len(second['allowed_development_gt']), 1)
        session = json.loads((self.candidate / 'inputs/session.json').read_text())
        self.assertFalse(any(row['target'] == '/development_gt' for row in session['readonly_mounts']))
        self.assertFalse((self.candidate / 'initial/system/configs/scenes.json').exists())
        self.assertFalse((self.candidate / 'initial/system/configs/experiment_01.json').exists())

    def test_previous_candidate_is_the_actual_initial_library(self):
        self.prepare()
        workspace = self.workspace()
        (workspace / 'library/engineering.md').write_text('Previous candidate marker; not a learned capability.\n')
        improvement.collect(self.candidate)
        source = self.candidate / 'candidate/library'
        before = {path.name: path.read_bytes() for path in source.iterdir()}
        next_candidate = self.root / 'experiments/capability_improvement/next'
        feedback = self.prepare(next_candidate, library=source, evidence=[])
        self.assertEqual(feedback['components']['source_library'], str(source))
        for path in source.iterdir():
            self.assertEqual((next_candidate / 'seed/library' / path.name).read_bytes(), before[path.name])
        self.assertTrue((next_candidate / 'initial/library/engineering.md').exists())
        self.assertEqual(feedback['candidate_history'], [])
        self.assertEqual(list((next_candidate / 'evidence').rglob('*')), [])
        (next_candidate / 'seed/library/engineering.md').write_text('New copy only.\n')
        self.assertEqual((source / 'engineering.md').read_bytes(), before['engineering.md'])

    def test_generic_input_has_no_condition_or_experiment_dependency(self):
        library = self.root / 'arbitrary-library'
        shutil.copytree(self.experiment / 'libraries/A3', library)
        input_file = self.root / 'generic.json'
        write(input_file, {'initial_library': 'arbitrary-library',
                          'feedback': 'experiments/experiment_03a_capability_acquisition/analysis/observed_results.json',
                          'budget': {'seconds': 17, 'calls': 2, 'cpus': [32], 'port': 19670}})
        shutil.rmtree(self.experiment / 'libraries')
        shutil.rmtree(self.experiment / 'configs')
        feedback = improvement.prepare(self.candidate, input_file)
        self.assertEqual(feedback['components']['source_library'], str(library))
        self.assertEqual(feedback['execution_budget']['seconds'], 17)
        self.assertEqual(feedback['candidate_history'], [])
        self.assertEqual(feedback['context'], {})
        self.assertNotIn('condition', feedback)

    def test_unselected_and_symlinked_evidence_is_not_copied(self):
        secret = self.root / 'development/S01/scene.blend'
        (self.experiment / 'runs/A-T01-A2/gt-link.blend').symlink_to(secret)
        feedback = self.prepare()
        paths = [row['source'] for row in json.loads((self.candidate / 'inputs/evidence_index.json').read_text())['files']]
        self.assertNotIn(str(secret), paths)
        self.assertFalse(any('gt-link' in path for path in paths))
        self.assertEqual(feedback['allowed_development_gt'], [])
        self.assertFalse((self.candidate / 'evidence/001/A-T01-A2/gt-link.blend').exists())
        self.assertFalse((self.candidate / 'evidence/001/A-T01-A2/backend_home/auth.json').exists())

    def test_text_only_and_existing_image_session_preparation(self):
        self.prepare()
        invocation = json.loads((self.candidate / 'inputs/invocation.json').read_text())
        prepare_isolated(invocation['directory'], invocation['image'], invocation['prompt'],
                         invocation['checkpoint'], invocation['session'])
        self.assertFalse((self.candidate / 'session/workspace/reference.png').exists())
        self.assertEqual(json.loads((self.candidate / 'session/inputs/images.json').read_text()), [])
        old = self.root / 'existing-image-session'
        image = self.root / 'development/S01/reference.png'
        prepare_isolated(old, image, 'Existing image behavior')
        self.assertEqual((old / 'workspace/reference.png').read_bytes(), image.read_bytes())
        self.assertEqual(json.loads((old / 'inputs/images.json').read_text()),
                         [{'path': '/app/reference.png', 'label': 'Reference image'}])

    def test_relative_evidence_symlinks_do_not_expand_access(self):
        (self.root / 'gt-link').symlink_to(self.root / 'development/S01', target_is_directory=True)
        input_file = self.root / 'relative-link.json'
        write(input_file, {'initial_library': str(self.experiment / 'libraries/A3'),
                          'feedback': str(self.experiment / 'analysis/observed_results.json'),
                          'evidence': ['gt-link'],
                          'budget': {'seconds': 17, 'calls': 2, 'cpus': [32], 'port': 19670}})
        with self.assertRaisesRegex(ValueError, 'not a symlink'):
            improvement.prepare(self.candidate, input_file)

    def test_external_evidence_on_another_filesystem_can_be_copied(self):
        with patch.object(improvement.os, 'link', side_effect=OSError(errno.EXDEV, 'Cross-device fixture')):
            self.prepare()
        self.assertEqual((self.candidate / 'evidence/001/A-T01-A2/capture/trajs.json').read_bytes(),
                         (self.experiment / 'runs/A-T01-A2/capture/trajs.json').read_bytes())

    def test_missing_selected_record_stays_unavailable(self):
        feedback = self.prepare(evidence=[self.root / 'unavailable.json'])
        self.assertEqual(feedback['unavailable_evidence'], ['/evidence/001/unavailable.json'])
        self.assertFalse((self.candidate / 'evidence/001/unavailable.json').exists())

    def test_previously_prepared_invocation_still_uses_its_saved_settings(self):
        self.prepare()
        invocation_path = self.candidate / 'inputs/invocation.json'
        invocation = json.loads(invocation_path.read_text())
        invocation['image'] = str(self.root / 'development/S01/reference.png')
        invocation['session']['condition'] = 'A3'
        write(invocation_path, invocation)
        def sdk_fixture(**arguments):
            self.assertEqual(arguments['image'], invocation['image'])
            self.assertEqual(arguments['session']['condition'], 'A3')
            self.workspace()
        with patch.object(improvement, 'execute', side_effect=sdk_fixture):
            improvement.run(self.candidate)
        self.assertEqual(json.loads((self.candidate / 'candidate.json').read_text())['file_changes'], [])


if __name__ == '__main__':
    unittest.main()
