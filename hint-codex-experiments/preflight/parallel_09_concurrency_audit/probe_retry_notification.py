"""Compare the same recoverable error event against frozen09 and the candidate."""
import asyncio
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
sys.path.insert(0, str(OUT))
from test_concurrency import InterleavedRPC, request
from test_retry_notifications import error_event


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


async def run(module):
    with tempfile.TemporaryDirectory() as directory:
        rpc = InterleavedRPC()
        bridge = module.CodexBridge(directory, rpc=rpc)
        async def recover(thread, turn):
            rpc.emit('error', error_event(thread, turn, True))
            await asyncio.sleep(.01)
            rpc.finish(thread)
        rpc.issue_tools = recover
        body = request('Complete after the native CLI retries its stream')
        body.pop('tools')
        outcome = {'bridge_source': module.__file__}
        try:
            response = await asyncio.wait_for(bridge.chat(body, route={
                'session': 'retry-probe', 'role': 'teacher', 'phase': 'generate'}), 2)
            outcome.update(bridge_returned='success', content=response['choices'][0]['message']['content'],
                           usage=response['usage'])
        except module.CodexBridgeError as exc:
            outcome.update(bridge_returned='error', error=str(exc))
        await bridge.close()
        state = next(iter(bridge.sessions.values()))
        outcome.update(native_completed=not state.active, error_retained=bool(state.error),
                       native_turn_starts=sum(method == 'turn/start' for method, _ in rpc.calls),
                       bridge_stopped=bridge.stopped)
        return outcome


async def main():
    schema = json.loads((ROOT / 'preflight/parallel_08_schema/v2/ErrorNotification.json').read_text())
    frozen = await run(load('retry_probe_frozen', ROOT / 'source_parallel_09/codex_cli_bridge.py'))
    changed = await run(load('retry_probe_candidate', OUT / 'candidate/codex_cli_bridge.py'))
    passed = (frozen['bridge_returned'] == 'error' and frozen['native_completed']
              and frozen['error_retained'] and changed['bridge_returned'] == 'success'
              and changed['native_completed'] and not changed['error_retained']
              and frozen['native_turn_starts'] == changed['native_turn_starts'] == 1)
    result = {'passed': passed, 'real_model_calls': 0, 'network_requests': 0,
              'required_protocol_field': 'willRetry' in schema['required'],
              'protocol_field_type': schema['properties']['willRetry']['type'],
              'frozen': frozen, 'candidate': changed}
    (OUT / 'retry_notification_probe.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    assert passed


if __name__ == '__main__':
    asyncio.run(main())
