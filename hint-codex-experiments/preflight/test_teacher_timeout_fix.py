#!/usr/bin/env python3
"""Check the teacher-only timeout patch in a temporary module, without models or Docker."""
import argparse
import importlib.util
import json
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
RELATIVE=Path("source/benchmark/deepswe/get_hint_by_task.py")
MODULE=None
WORK=None

class FakeContainer:
    name="offline-teacher"
    def __init__(self,directory,metadata,live_timeout=False):
        self.artifact=directory/"container_trajs.json"
        self.metadata=metadata
        self.live_timeout=live_timeout
        self.commands=[]
        self.exit_code=None

    def exec_run(self,command,**kwargs):
        if isinstance(command,str) and command.startswith("mkdir -p "):
            return 0,b""
        self.commands.append(command)
        if self.live_timeout:
            code=("import json,time; from pathlib import Path\n"
                  "try:\n while True: time.sleep(1)\n"
                  "except KeyboardInterrupt:\n Path("+repr(str(self.artifact))+").write_text("
                  +repr(json.dumps({"metadata":{"status":"incomplete","error_log":"Interrupted"}}))+")\n")
            actual=list(command[:-1])+[shlex.join([sys.executable,"-c",code])]
            result=subprocess.run(actual,capture_output=True,timeout=5)
            self.exit_code=result.returncode
            return result.returncode,result.stdout+result.stderr
        self.artifact.write_text(json.dumps({"metadata":self.metadata}))
        self.exit_code=0
        return 0,b""


def copy_artifact(container,source,destination):
    if source.endswith("/trajs.json") and container.artifact.exists():
        shutil.copyfile(container.artifact,Path(destination)/"trajs.json")
        return True
    return False


class TeacherTimeoutTests(unittest.TestCase):
    def generator(self,metadata=None,live_timeout=False):
        directory=Path(tempfile.mkdtemp(dir=WORK))
        generator=MODULE.ContainerHintGenerator.__new__(MODULE.ContainerHintGenerator)
        generator.out_dir=directory
        generator.monitor_interval=0
        generator.base_commit="offline-base"
        generator.instance_id="offline-task"
        generator.args=SimpleNamespace(config="unused",provider="openai",model="gpt-6.1-terra",
                                       teacher_state=str(directory/"teacher_state.json"),keep_teacher=True)
        generator.container=FakeContainer(directory,metadata or {
            "status":"completed","ResultMessage":{"subtype":"success","is_error":False,"session_id":"offline-session"}},live_timeout)
        return generator

    def pipeline(self,generator,execution_ok,hint):
        for name in ("load_task_row","start_container","inject_files","install_and_reset",
                     "make_repository_read_only","save_hint","save_teacher_state","clear_stage_files",
                     "stop_and_remove_container"):
            setattr(generator,name,Mock())
        generator.run_hint_agent=Mock(return_value=execution_ok)
        generator.collect_hint=Mock(return_value=hint)
        config=SimpleNamespace(resolve_task=lambda:None)
        with patch.object(MODULE,"load_run_config",return_value=config):
            return generator.run()

    def test_normal_teacher_and_resume_keep_successful_session(self):
        generator=self.generator()
        with patch.object(MODULE,"copy_from_container",side_effect=copy_artifact),patch.object(MODULE,"HINT_TASK_TIMEOUT_SEC",3600):
            self.assertTrue(generator.run_hint_agent(None))
            self.assertEqual(generator.container.commands[-1][:8],
                             ["timeout","-s","INT","-k","30","3600","/bin/bash","-c"])
            self.assertTrue(generator.run_hint_agent(None,output_dir_in_container="/tmp/teacher_review_out",
                                                     resume_session_id="offline-session"))
            self.assertIn("--resume_session_id offline-session",generator.container.commands[-1][-1])
            self.assertIn("--output_dir /tmp/teacher_review_out",generator.container.commands[-1][-1])
        self.assertEqual(self.pipeline(generator,True,"Complete English guidance"),0)
        generator.save_teacher_state.assert_called_once()
        generator.clear_stage_files.assert_called_once()
        generator.stop_and_remove_container.assert_not_called()

    def test_real_timeout_interrupts_and_saves_partial_artifact(self):
        generator=self.generator(live_timeout=True)
        with patch.object(MODULE,"copy_from_container",side_effect=copy_artifact),patch.object(MODULE,"HINT_TASK_TIMEOUT_SEC",0.5):
            self.assertFalse(generator.run_hint_agent(None))
        self.assertEqual(generator.container.exit_code,124)
        metadata=json.loads((generator.out_dir/"trajs.json").read_text())["metadata"]
        self.assertEqual(metadata["status"],"incomplete")
        self.assertEqual(metadata["error_log"],"Interrupted")

    def test_process_zero_does_not_accept_failed_or_missing_sdk_result(self):
        cases=[{"status":"incomplete","ResultMessage":{"is_error":True}},
               {"status":"completed","ResultMessage":{"is_error":True}},
               {"status":"completed"}]
        for metadata in cases:
            with self.subTest(metadata=metadata):
                generator=self.generator(metadata)
                with patch.object(MODULE,"copy_from_container",side_effect=copy_artifact):
                    self.assertFalse(generator.run_hint_agent(None))
                self.assertEqual(generator.container.exit_code,0)

    def test_partial_hint_never_succeeds_or_preserves_teacher(self):
        generator=self.generator()
        self.assertEqual(self.pipeline(generator,False,"Partial English guidance already written"),1)
        generator.collect_hint.assert_called_once()
        generator.save_hint.assert_called_once_with("Partial English guidance already written")
        generator.save_teacher_state.assert_not_called()
        generator.clear_stage_files.assert_not_called()
        generator.stop_and_remove_container.assert_called_once()


def main():
    global MODULE,WORK
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--applied",action="store_true",help="Test an already patched source copy without reapplying the patch")
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="teacher-timeout-fix-") as directory:
        WORK=Path(directory)
        target=WORK/RELATIVE
        target.parent.mkdir(parents=True)
        shutil.copyfile(ROOT/RELATIVE,target)
        if not args.applied:
            subprocess.run(["patch","--batch","--silent","-p1","--input",str(ROOT/"preflight/teacher_timeout_fix.patch")],
                           cwd=WORK,check=True)
        sys.path.insert(0,str(ROOT/"source"))
        spec=importlib.util.spec_from_file_location("teacher_timeout_temporary_fixture",target)
        MODULE=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(MODULE)
        suite=unittest.defaultTestLoader.loadTestsFromTestCase(TeacherTimeoutTests)
        result=unittest.TextTestRunner(verbosity=2).run(suite)
        return 0 if result.wasSuccessful() else 1

if __name__=="__main__":
    raise SystemExit(main())
