"""Exercise branch setup and patch export with a real temporary Git repository."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / "source_parallel_13"
sys.path.insert(0, str(SOURCE))
import run_cc_sdk as sdk


class WorkspaceExecutionTests(unittest.IsolatedAsyncioTestCase):
    async def test_detached_master_becomes_main_and_committed_fix_is_exported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository = root / "repository"
            repository.mkdir()
            env = {"GIT_CONFIG_GLOBAL": str(root / "gitconfig"), "TEACHER_MODE": "0"}
            with patch.dict(os.environ, env):
                def git(*args):
                    return subprocess.check_output(["git", *args], cwd=repository,
                                                   stderr=subprocess.STDOUT, text=True).strip()
                git("init", "-q")
                git("symbolic-ref", "HEAD", "refs/heads/master")
                git("config", "user.name", "Fixture")
                git("config", "user.email", "fixture@example.invalid")
                (repository / "answer.py").write_text("answer = 1\n")
                git("add", ".")
                git("commit", "-qm", "Initial")
                base = git("rev-parse", "HEAD")
                git("checkout", "--detach", base)
                observations = {}

                class Client:
                    def __init__(self, options):
                        pass

                    async def __aenter__(self):
                        return self

                    async def __aexit__(self, *args):
                        pass

                    async def query(self, prompt):
                        observations["branch"] = git("branch", "--show-current")
                        observations["base"] = git("rev-parse", "HEAD")
                        observations["initial_diff"] = git("diff", base)
                        git("checkout", "-b", "fixture-fix", "main")
                        (repository / "answer.py").write_text("answer = 2\n")
                        git("add", "answer.py")
                        git("commit", "-qm", "Fix answer")

                    async def receive_response(self):
                        for message in ():
                            yield message

                with patch.object(sdk, "ClaudeSDKClient", Client):
                    await sdk.run_agent_execution("Implement the fix", str(repository), None,
                                                  base_commit=base, commit_file=str(root / "base.txt"))
                self.assertEqual(observations, {"branch": "main", "base": base, "initial_diff": ""})
                self.assertEqual((root / "base.txt").read_text().strip(), base)
                self.assertEqual(git("diff"), "")
                exported = sdk.get_smart_diff(str(repository), base).decode()
                self.assertIn("-answer = 1", exported)
                self.assertIn("+answer = 2", exported)

                class ResumeClient(Client):
                    async def query(self, prompt):
                        observations["resume_branch"] = git("branch", "--show-current")
                        observations["resume_source"] = (repository / "answer.py").read_text()

                with patch.object(sdk, "ClaudeSDKClient", ResumeClient):
                    await sdk.run_agent_execution("Continue", str(repository), None,
                                                  base_commit=base, is_resume=True,
                                                  extra_message="Review the existing changes",
                                                  commit_file=str(root / "base.txt"))
                self.assertEqual(observations["resume_branch"], "fixture-fix")
                self.assertEqual(observations["resume_source"], "answer = 2\n")
                self.assertEqual((root / "base.txt").read_text().strip(), base)

    async def test_teacher_initialization_does_not_mutate_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            class Client:
                def __init__(self, options):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    pass

                async def query(self, prompt):
                    pass

                async def receive_response(self):
                    for message in ():
                        yield message

            with patch.dict(os.environ, {"TEACHER_MODE": "1"}), \
                    patch.object(sdk, "ClaudeSDKClient", Client), \
                    patch.object(sdk, "run_command") as command:
                await sdk.run_agent_execution("Analyze only", directory, None, base_commit="fixture")
            command.assert_not_called()
            self.assertEqual(list(Path(directory).iterdir()), [])

    async def test_sdk_keeps_tools_and_hooks_but_disables_skill_discovery(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(sdk, "SYSTEM_PROMPT_CONFIG_LOG_PATH", Path(directory) / "prompt.json"):
            options = sdk.create_agent_options(directory)
        self.assertEqual(options.extra_args, {"disable-slash-commands": None})
        self.assertIn("Skill", options.disallowed_tools)
        self.assertEqual(options.setting_sources, ["user", "project"])
        self.assertEqual(options.permission_mode, "bypassPermissions")
        self.assertTrue(options.sandbox["enabled"])

    async def test_workspace_setup_failure_is_not_silently_ignored(self):
        with self.assertRaises(subprocess.CalledProcessError):
            sdk.run_command("exit 17")

    async def test_native_catalog_keeps_model_and_window_with_no_execution_tools(self):
        models = json.loads((SOURCE / "codex_model_catalog.json").read_text())["models"]
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["slug"], "gpt-6.1-terra")
        self.assertEqual(models[0]["tool_mode"], "direct")
        self.assertIsNone(models[0]["apply_patch_tool_type"])
        self.assertEqual(models[0]["experimental_supported_tools"], [])
        self.assertEqual(models[0]["context_window"], 500000)
        self.assertEqual(models[0]["effective_context_window_percent"], 95)


if __name__ == "__main__":
    unittest.main()
