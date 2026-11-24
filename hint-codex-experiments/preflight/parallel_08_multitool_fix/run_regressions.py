"""Run existing bridge and tool-transport fixtures against the isolated candidate."""

import importlib.util
import json
import os
import socket
import sys
import time
import unittest
from pathlib import Path

os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
os.environ["LITELLM_TELEMETRY"] = "False"
network_attempts = []


def no_connect(self, address):
    network_attempts.append(str(address))
    raise RuntimeError("Network disabled for candidate regressions")


socket.socket.connect = no_connect
socket.socket.connect_ex = no_connect
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
spec = importlib.util.spec_from_file_location("codex_cli_bridge", OUT / "codex_cli_bridge.py")
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)
sys.path.insert(0, str(ROOT / "tests_parallel_08_static"))
suite = unittest.TestSuite()
for name in ("test_codex_cli_bridge", "test_tool_result_transport"):
    suite.addTests(unittest.defaultTestLoader.loadTestsFromName(name))
started = time.monotonic()
with (OUT / "regressions.log").open("w") as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
record = {"passed": result.wasSuccessful() and not network_attempts, "tests": result.testsRun,
          "failures": len(result.failures), "errors": len(result.errors),
          "elapsed_seconds": time.monotonic() - started, "network_attempts": network_attempts,
          "model_calls": 0, "candidate_module": module.__file__}
(OUT / "regressions.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record))
raise SystemExit(0 if record["passed"] else 1)
