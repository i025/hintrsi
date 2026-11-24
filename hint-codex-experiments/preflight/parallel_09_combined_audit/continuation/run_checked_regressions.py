"""Run the checked production source, never an earlier independent candidate."""
import importlib
import importlib.util
import json
import os
import sys
import time
import unittest
from pathlib import Path

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = 'True'
os.environ['TELEMETRY'] = 'False'
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = ROOT / 'source_parallel_09_checked'
TESTS = ROOT / 'tests_parallel_09_checked'
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(OUT))
import codex_cli_bridge
assert Path(codex_cli_bridge.__file__).resolve() == SOURCE / 'codex_cli_bridge.py'
suite = unittest.defaultTestLoader.discover(str(TESTS), pattern='test_*.py')
assert suite.countTestCases() == 106
counts = {}
for name in ('test_concurrency', 'test_response_delivery', 'test_retry_notifications',
             'test_late_results', 'test_combined_delivery'):
    spec = importlib.util.spec_from_file_location(name, OUT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    tests = unittest.defaultTestLoader.loadTestsFromModule(module)
    counts[name] = tests.countTestCases()
    suite.addTests(tests)
assert sys.modules['test_response_delivery'].candidate is codex_cli_bridge
assert sys.modules['test_concurrency'].CodexBridge is codex_cli_bridge.CodexBridge
assert sys.modules['test_late_results'].CodexBridge is codex_cli_bridge.CodexBridge
paths = {name: str(Path(module.__file__).resolve()) for name, module in list(sys.modules.items())
         if getattr(module, '__file__', None) and Path(module.__file__).is_file()
         and str(ROOT) in str(Path(module.__file__).resolve())}
unexpected = {name: path for name, path in paths.items()
              if not (path.startswith(str(SOURCE) + '/') or path.startswith(str(TESTS) + '/')
                      or path.startswith(str(OUT) + '/'))}
assert not unexpected, unexpected
started = time.monotonic()
with (OUT / 'all_tests.log').open('w') as stream:
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
record = {'passed': result.wasSuccessful(), 'tests': result.testsRun, 'failures': len(result.failures),
          'errors': len(result.errors), 'elapsed_seconds': time.monotonic() - started,
          'original_tests': 106, 'additional_counts': counts, 'actual_modules': paths,
          'unexpected_project_modules': unexpected, 'real_model_calls': 0,
          'production_modified': False, 'formal_experiment_started': False,
          'checkpoint_adjustment': 'Expect checked lifecycle field recovered_tool_results; last_request/last_response remain excluded.'}
(OUT / 'all_tests.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({key: value for key, value in record.items() if key != 'actual_modules'}, indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
