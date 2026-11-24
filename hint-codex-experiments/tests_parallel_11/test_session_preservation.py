"""Check preservation of conversations and containers without calling models."""
import asyncio
import gzip
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "source_parallel_11"))
from benchmark.deepswe.get_hint_by_task import ContainerHintGenerator
from run_codex_experiments import PairedExperiments
from run_parallel_experiments import ParallelExperiments

class SessionPreservationTests(unittest.TestCase):
    def test_sdk_archive_preserves_conversation_and_subagent_files(self):
        with tempfile.TemporaryDirectory() as directory:
            buffer = io.BytesIO()
            files = {"projects/-app/session.jsonl": b'{"uuid":"message-1"}\n',
                     "projects/-app/session/subagents/agent-a.jsonl": b'{"uuid":"child-1"}\n'}
            with tarfile.open(fileobj=buffer, mode="w") as archive:
                for name, content in files.items():
                    member = tarfile.TarInfo(name)
                    member.size = len(content)
                    archive.addfile(member, io.BytesIO(content))
            teacher = ContainerHintGenerator.__new__(ContainerHintGenerator)
            teacher.out_dir = Path(directory)
            teacher.container = Mock()
            content = buffer.getvalue()
            teacher.container.get_archive.return_value = (iter([content[:100], content[100:]]), {})
            path = teacher.save_sdk_session()
            with tarfile.open(path, "r:gz") as archive:
                self.assertEqual({m.name: archive.extractfile(m).read() for m in archive.getmembers()}, files)
            teacher.container.get_archive.assert_called_once_with("/root/.claude/projects")

    def test_stopped_worker_keeps_exactly_its_own_containers(self):
        driver = PairedExperiments.__new__(PairedExperiments)
        driver.args = SimpleNamespace(dry_run=False, experiment_name="preserved-worker")
        driver.state = {"status":"stopped"}
        driver.kept_teachers = []
        container = Mock(name="teacher")
        container.name = "preserved-teacher"
        client = Mock()
        client.containers.list.return_value = [container]
        with patch("docker.from_env", return_value=client):
            driver.close_teachers()
        container.stop.assert_called_once_with(timeout=10)
        container.remove.assert_not_called()
        client.containers.list.assert_called_once_with(all=True, filters={"label":"hint.experiment_name=preserved-worker"})
        self.assertEqual(driver.state["retained_containers"], ["preserved-teacher"])

    def test_coordinator_does_not_delete_stopped_worker_containers(self):
        driver = ParallelExperiments.__new__(ParallelExperiments)
        driver.args = SimpleNamespace(dry_run=False)
        process = Mock()
        process.poll.return_value = 2
        driver.processes = {0:process}
        driver.workers = [{"lane":0,"experiment":"preserved-worker","docker_host":"unix:///fixture"}]
        client, container = Mock(), Mock()
        client.containers.list.return_value = [container]
        with patch("docker.DockerClient", return_value=client):
            driver.stop_workers()
        container.stop.assert_called_once_with(timeout=10)
        container.remove.assert_not_called()

if __name__ == "__main__":
    unittest.main()
