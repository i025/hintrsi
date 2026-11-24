"""Offline tests for the preexperiment materials and evidence classification."""
import errno
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import audit_stages
import controller
import m_i_guest
import stage_materials
from get_hint_by_task import HINT_AGENT_SYSTEM_PROMPT, HINT_AGENT_USER_PROMPT
from review_hint_traj import REVIEW_SYSTEM_PROMPT_SOLVED


class StageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.fixture = self.root / 'fixture'
        (self.fixture / 'data').mkdir(parents=True)
        (self.fixture / 'window_report.py').write_text("value = record['time'] < end\n")
        for index in range(20):
            (self.fixture / 'data' / f'shard_{index:02d}.json').write_text('[{"time": 2, "value": 7}]')
        self.issue = self.root / 'issue.txt'
        self.issue.write_text('Include both endpoints.')
        self.hint = self.root / 'hint.md'
        self.hint.write_text('Examine boundary behavior.')
        self.materials = self.root / 'materials'
        stage_materials.initial(self.issue, self.fixture, self.materials)

    def test_original_teacher_prompts_and_reference_are_preserved(self):
        self.assertEqual((self.materials / 'teacher_system.md').read_text(), HINT_AGENT_SYSTEM_PROMPT)
        self.assertEqual((self.materials / 'teacher_initial.md').read_text(), HINT_AGENT_USER_PROMPT.format(
            golden_diff_path='/tmp/golden_diff.diff', problem_statement=self.issue.read_text(), hint_output_path='/tmp/hint_output.md'))
        golden = (self.materials / 'golden_diff.diff').read_text()
        self.assertIn("-value = record['time'] < end", golden)
        self.assertIn("+value = record['time'] <= end", golden)
        self.assertEqual((self.fixture / 'window_report.py').read_text(), "value = record['time'] < end\n")

    def test_online_student_has_twenty_reads_but_no_reference(self):
        output = self.root / 'online'
        stage_materials.online(self.issue, self.fixture, self.hint, self.materials / 'golden_diff.diff', output,
                               'fixture-I', 'fixture', 'http://127.0.0.1:8765/v1')
        student = (output / 'student_problem.txt').read_text()
        self.assertEqual(student.count('/app/data/shard_'), 20)
        self.assertNotIn('golden_diff', student)
        self.assertNotIn("record['time']", student)
        manifest = json.loads((output / 'online_manifest.json').read_text())
        self.assertEqual([manifest[key] for key in ('checkpoint_tools', 'max_checks', 'check_timeout_seconds')], [20, 3, 600])
        registration = json.loads((output / 'registration.json').read_text())
        self.assertEqual(registration['golden_diff'], (self.materials / 'golden_diff.diff').read_text())

    def test_review_uses_original_solved_prompt_and_real_trajectory(self):
        trajs = self.root / 'trajs.json'
        trajs.write_text(json.dumps({'messages': [{'role': 'user', 'content': 'Fix it.'},
            {'role': 'assistant', 'content': 'The actual repair passed.'}]}))
        output = self.root / 'review'
        stage_materials.review(trajs, self.hint, self.materials / 'golden_diff.diff', output, solved=True)
        text = (output / 'teacher_review.md').read_text()
        self.assertTrue(text.startswith(REVIEW_SYSTEM_PROMPT_SOLVED))
        self.assertIn('The actual repair passed.', text)
        self.assertIn(self.hint.read_text(), text)
        self.assertIn('/tmp/review_output.md', text)

    def test_teacher_audit_requires_history_not_only_session_id(self):
        initial, review, bridge = [self.root / name for name in ('M_initial', 'M_review', 'bridge')]
        for path in (initial, review, bridge):
            path.mkdir()
        for path, started, finished in ((initial, 1, 5), (review, 10, 15)):
            (path / 'stage_result.json').write_text(json.dumps({'sdk_session_id': 'same-sdk', 'sdk_completed': True,
                'readonly_checks': [{'readonly_mount': True}], 'started_at_unix': started, 'finished_at_unix': finished}))
        final = 'First hint.\nSecond line.'
        responses = [{'timestamp': 2, 'session': 'm', 'response': {'choices': [{'message': {'tool_calls': [{'id': 'read-1'}]}}]}},
                     {'timestamp': 4, 'session': 'm', 'response': {'choices': [{'message': {'content': final}}]}}]
        (bridge / 'model_responses.jsonl').write_text('\n'.join(map(json.dumps, responses)))
        request = {'timestamp': 11, 'session': 'm', 'request_id': 'review-1', 'request': {'messages': [
            {'role': 'tool', 'tool_call_id': 'read-1', 'content': 'Real source.'}, {'role': 'assistant', 'content': final}]}}
        target = bridge / 'model_requests.jsonl'
        target.write_text(json.dumps(request) + '\n')
        self.assertTrue(audit_stages.teacher(initial, review, bridge, 'm')['passed'])
        request['request']['messages'] = [{'role': 'user', 'content': 'Review now.'}]
        target.write_text(json.dumps(request) + '\n')
        self.assertFalse(audit_stages.teacher(initial, review, bridge, 'm')['passed'])

    def online_evidence(self, decision, inject):
        student, progress, bridge = [self.root / name for name in ('student', 'progress', 'bridge')]
        for path in (student, progress, bridge):
            path.mkdir(exist_ok=True)
        (student / 'stage_result.json').write_text(json.dumps({'sdk_completed': True}))
        (student / 'online_teacher_state.json').write_text(json.dumps({'checks': 1, 'tool_count': 23}))
        events = [{'tool_name': 'Read', 'tool_input': {'file_path': f'/app/data/shard_{i:02d}.json'}} for i in range(20)] + [{'check': 1}]
        (student / 'online_teacher_events.json').write_text(json.dumps(events))
        hint = 'Check boundaries.\nUse observed behavior.' if decision == 'delivered' else ''
        check = {'session': 'i', 'check': 1, 'tool_count': 20, 'decision': decision, 'hint': hint,
                 'duration_seconds': 5, 'stopped': False, 'finished_at': 4}
        (progress / 'progress.jsonl').write_text(json.dumps(check) + '\n')
        request = {'session': 'i', 'role': 'student', 'request_id': 'i-next', 'timestamp': 5,
                   'request': {'messages': [{'role': 'tool', 'content': 'Teacher guidance:\n' + hint if inject else 'File data'}]}}
        (bridge / 'model_requests.jsonl').write_text(json.dumps(request) + '\n')
        return audit_stages.online(student, progress, bridge, 'i')

    def test_no_hint_passes_checkpoint_but_does_not_claim_injection(self):
        evidence = self.online_evidence('no_hint_needed', False)
        self.assertTrue(evidence['passed'])
        self.assertFalse(evidence['actual_guidance_injection_verified'])
        self.assertEqual(evidence['guidance_injection_coverage'], 'not_exercised')

    def test_delivered_hint_requires_downstream_observation(self):
        self.assertFalse(self.online_evidence('delivered', False)['passed'])
        evidence = self.online_evidence('delivered', True)
        self.assertTrue(evidence['passed'])
        self.assertTrue(evidence['actual_guidance_injection_verified'])

    def test_readonly_check_requires_kernel_readonly_mount_without_writing(self):
        source = self.fixture / 'window_report.py'
        before = source.read_bytes()
        self.assertFalse(m_i_guest.readonly(str(source))['readonly_mount'])
        self.assertEqual(source.read_bytes(), before)
        with patch('m_i_guest.os.open', side_effect=OSError(errno.EROFS, 'Read-only filesystem')):
            self.assertTrue(m_i_guest.readonly(str(source))['readonly_mount'])
        with patch('m_i_guest.os.open', side_effect=PermissionError(errno.EACCES, 'Permission denied')):
            self.assertFalse(m_i_guest.readonly(str(source))['readonly_mount'])



if __name__ == '__main__':
    unittest.main(verbosity=2)
