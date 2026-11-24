"""Execute the SDK CLI's long-prompt transport without starting a model."""

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "source_parallel_10"
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / "benchmark" / "deepswe"))
import get_hint_by_task  # noqa: E402
import run_multi_turn_loop  # noqa: E402
import run_cc_trajs_swe_pro  # noqa: E402

ExecResult = namedtuple("ExecResult", "exit_code output")


class LocalContainer:
    """Run the existing command templates locally with only run_sdk replaced."""

    name = "offline-prompt-transport"

    def __init__(self, root):
        self.root = root
        self.path("/app").mkdir(parents=True)
        self.path("/tmp").mkdir(parents=True)
        self.path("/tmp/sdk_script.py").write_text(
            "import json,sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(SOURCE)!r})\n"
            "import run_cc_sdk\n"
            "async def capture(**kwargs):\n"
            "    output = kwargs['output_dir']\n"
            "    output.mkdir(parents=True, exist_ok=True)\n"
            "    values = {key: kwargs[key] for key in "
            "('problem_statement', 'extra_message', 'resume_session_id')}\n"
            "    (output/'captured.json').write_text(json.dumps(values), encoding='utf-8')\n"
            "    (output/'trajs.json').write_text(json.dumps({'metadata': "
            "{'status':'completed','ResultMessage':{'is_error':False,'session_id':'offline'}}}))\n"
            "run_cc_sdk.run_sdk = capture\n"
            "run_cc_sdk.anyio.run(run_cc_sdk.main)\n"
        )

    def path(self, remote):
        return self.root / remote.lstrip("/")

    def translate(self, text):
        return (text.replace("/opt/python3.12-tmp/bin/python3", shlex.quote(sys.executable))
                    .replace("/tmp", str(self.path("/tmp")))
                    .replace("/app", str(self.path("/app"))))

    def exec_run(self, command, workdir=None, environment=None):
        if isinstance(command, list):
            command = [self.translate(part) for part in command]
            use_shell = False
        else:
            command = self.translate(command)
            use_shell = True
        result = subprocess.run(command, shell=use_shell, capture_output=True,
                                env={**os.environ, **(environment or {})}, timeout=20)
        return ExecResult(result.returncode, result.stdout + result.stderr)

    def inject(self, container, data, remote):
        path = self.path(remote)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def copy(self, container, remote, destination):
        shutil.copy2(self.path(remote), Path(destination) / Path(remote).name)
        return True


class PromptFileTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.container = LocalContainer(self.root / "guest")
        # The payload is above Linux's single-argument limit. Quotes and shell
        # expressions must remain data, including internal and trailing CRLF.
        self.payload = (("Unicode 教师; 'quotes' \"double\" $(printf wrong) `printf wrong`\r\n" * 3500)
                        + "final space \t\r\n\n").encode("utf-8")
        self.assertGreater(len(self.payload), 128 * 1024)
        self.expected = self.payload.decode("utf-8").rstrip("\n")

    def tearDown(self):
        self.temp.cleanup()

    def captured(self, remote):
        return json.loads(self.container.path(remote).read_text())

    def test_teacher_fresh_and_resume_execute_large_file_arguments(self):
        runner = get_hint_by_task.ContainerHintGenerator.__new__(get_hint_by_task.ContainerHintGenerator)
        runner.container = self.container
        runner.out_dir = self.root / "teacher-output"
        runner.out_dir.mkdir()
        runner.base_commit = "fixture-base"
        runner.monitor_interval = 0
        with patch.object(get_hint_by_task, "inject_file_to_container", self.container.inject), \
                patch.object(get_hint_by_task, "copy_from_container", self.container.copy):
            for session in (None, "original-sdk-session"):
                with self.subTest(session=session):
                    self.assertTrue(runner.run_hint_agent(None, user_prompt=self.payload.decode("utf-8"),
                                                         resume_session_id=session))
                    captured = self.captured("/tmp/hint_agent_out/captured.json")
                    self.assertEqual(captured["problem_statement"], self.expected)
                    self.assertEqual(captured["extra_message"], self.expected if session else None)
                    self.assertEqual(captured["resume_session_id"], session)
                    self.assertEqual(self.container.path("/tmp/ps.txt").read_bytes(), self.payload)

    def test_student_fresh_and_resume_use_the_same_large_file_transport(self):
        runner = run_multi_turn_loop.MultiTurnLoopRunner.__new__(run_multi_turn_loop.MultiTurnLoopRunner)
        runner.container = self.container
        runner.args = SimpleNamespace(experiment_session="", teacher_progress_url="", first_init=False)
        runner.compact_hint_path = None
        runner.base_commit = "fixture-base"
        runner.session_id = "original-sdk-session"
        runner.monitor_interval = 0
        runner.execution_status = {}
        self.container.inject(None, self.payload, "/tmp/ps.txt")
        with patch.object(run_multi_turn_loop, "inject_file_to_container", self.container.inject):
            self.assertTrue(runner.execute_turn(1, None))
            self.assertEqual(self.captured("/tmp/turn_1/captured.json")["problem_statement"], self.expected)
            self.assertTrue(runner.execute_turn(2, None, hint=self.payload.decode("utf-8")))
        captured = self.captured("/tmp/turn_2/captured.json")
        self.assertEqual(captured["extra_message"], self.expected)
        self.assertEqual(captured["resume_session_id"], "original-sdk-session")
        self.assertEqual(self.container.path("/tmp/hint_turn_2.txt").read_bytes(), self.payload)
        self.assertEqual(self.container.path("/tmp/ps.txt").read_bytes(), self.payload)

    def test_single_run_student_executes_large_file_argument(self):
        runner = run_cc_trajs_swe_pro.DockerTaskRunner.__new__(run_cc_trajs_swe_pro.DockerTaskRunner)
        runner._system_prompt_content = None
        self.container.inject(None, self.payload, "/tmp/ps.txt")
        status, _, exit_code, _ = runner._execute_task(self.container, "offline-task", "fixture-base", {})
        self.assertEqual((status, exit_code), ("success", 0))
        self.assertEqual(self.captured("/tmp/captured.json")["problem_statement"], self.expected)
        self.assertEqual(self.container.path("/tmp/ps.txt").read_bytes(), self.payload)

    def test_file_mode_matches_shell_lf_semantics_and_legacy_text_is_unchanged(self):
        capture = self.container.path("/tmp/sdk_script.py")
        for number, text in enumerate(("line\r\nlast\r\n\n", "line\nlast\n\n", "last\r", "last \t")):
            with self.subTest(text=repr(text)):
                prompt = self.root / f"short-{number}.txt"
                prompt.write_bytes(text.encode("utf-8"))
                previous = subprocess.run(["/bin/bash", "-c", 'printf %s "$(cat "$1")"', "fixture", str(prompt)],
                                          capture_output=True, check=True).stdout
                output = self.root / f"file-output-{number}"
                result = subprocess.run([sys.executable, str(capture), "--cwd", str(self.root),
                                         "--problem_statement_file", str(prompt), "--output_dir", str(output),
                                         "--log_path", str(self.root / "offline.log")], capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
                self.assertEqual(json.loads((output / "captured.json").read_text())["problem_statement"].encode("utf-8"), previous)
                self.assertEqual(prompt.read_bytes(), text.encode("utf-8"))
        direct = "legacy text with CRLF\r\n\n"
        output = self.root / "legacy-output"
        result = subprocess.run([sys.executable, str(capture), "--cwd", str(self.root),
                                 "--problem_statement", direct, "--output_dir", str(output),
                                 "--log_path", str(self.root / "offline.log")], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads((output / "captured.json").read_text())["problem_statement"], direct)
        result = subprocess.run([sys.executable, str(capture), "--cwd", str(self.root),
                                 "--resume_session_id", "legacy-sdk-session", "--extra_message", direct,
                                 "--output_dir", str(output), "--log_path", str(self.root / "offline.log")],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(json.loads((output / "captured.json").read_text())["extra_message"], direct)


if __name__ == "__main__":
    unittest.main()
