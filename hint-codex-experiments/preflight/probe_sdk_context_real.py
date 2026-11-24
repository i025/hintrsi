#!/usr/bin/env python3
"""Check one real SDK additionalContext delivery without changing teacher policy."""

import argparse
import json
import time

import docker

from probe_sdk_bridge import ROOT, SOURCE, PYTHON, copy_file, put_file, status
from probe_sdk_online_real import NATIVE_ITEMS, occurrences
from constant_zhy import render_proxy_config

SESSION = "preflight-context-real"
NAME = "codex-sdk-context-real-preflight"
OUT = ROOT / "preflight/sdk_context_real"
FILE_MARKER = "TOOL_ORIGINAL_MARKER_W72"
CONTEXT_MARKER = "CONTEXT_MARKER_20261121_R4"
PROMPT = (
    "Run a one-read protocol check. Use Read exactly once on /app/evidence.txt. "
    "Do not use other tools or modify files. Then report CONTEXT_GATE_COMPLETE, "
    "the file marker, and any additional context marker received after the read. "
    "Report each marker once and stop."
)
GUEST = '''import asyncio
import copy
import json
import sys
import time
from pathlib import Path

from claude_agent_sdk import HookMatcher
from logging_utils import setup_logging
from sdk_script import create_agent_options, run_agent_execution

OUT = Path('/tmp/context_gate_out')
CONTEXT_MARKER = 'CONTEXT_MARKER_20261121_R4'
PROMPT = json.loads(Path('/tmp/query.json').read_text())


async def main():
    setup_logging('/tmp/sdk_script.log')
    events = []
    trajectories = {'main_agent': '', 'sub_agent': []}
    metadata = {}
    started = time.monotonic()

    async def fixed_context(data, tool_use_id, context):
        before = copy.deepcopy(data['tool_response'])
        result = {'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': 'Transport check reminder: ' + CONTEXT_MARKER + '. Keep the file unchanged.',
        }}
        events.append({'tool_use_id': tool_use_id, 'tool_name': data['tool_name'],
                       'tool_response': before, 'response_unchanged': data['tool_response'] == before,
                       'hook_output': result})
        return result

    options = create_agent_options('/app')
    options.hooks = {'PostToolUse': [HookMatcher(hooks=[fixed_context])]}
    try:
        await run_agent_execution(PROMPT, '/app', options, base_commit=sys.argv[1],
                                  trajectories=trajectories, metadata=metadata)
        metadata['status'] = 'completed' if ('ResultMessage' in metadata
                    and not metadata['ResultMessage'].get('is_error')) else 'incomplete'
    except BaseException as exc:
        metadata['status'] = 'incomplete'
        metadata['error'] = str(exc) or type(exc).__name__
        raise
    finally:
        metadata['wall_seconds'] = time.monotonic() - started
        (OUT / 'trajs.json').write_text(json.dumps({'metadata': metadata,
                                                  'trajectories': trajectories}, indent=2))
        (OUT / 'hook_events.json').write_text(json.dumps(events, indent=2))


asyncio.run(main())
'''


def save_records(result):
    rows = {}
    for name in ('model_requests.jsonl', 'model_responses.jsonl', 'codex_events.jsonl', 'token_usage.jsonl'):
        path = ROOT / 'logs/bridge' / name
        rows[name] = [row for line in path.open() if (row := json.loads(line)).get('session') == SESSION]
        (OUT / name).write_text(''.join(json.dumps(row) + '\n' for row in rows[name]))
    result['native_tool_event_count'] = sum(
        row['event'].get('params', {}).get('item', {}).get('type') in NATIVE_ITEMS
        or any(row['event'].get('method', '').startswith('item/' + name + '/') for name in NATIVE_ITEMS)
        for row in rows['codex_events.jsonl'])
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        print(json.dumps({'prepared': True, 'session': SESSION, 'real_model_calls': 0,
                          'purpose': 'Fixed additionalContext transport only; production 20/3 policy unchanged'}))
        return
    before = status()
    assert not before['stopped'], before['stop_reason']
    assert not any(row['session'] == SESSION for row in before['sessions'])
    OUT.mkdir(parents=True)
    result = {'session': SESSION, 'purpose': 'One-read fixed additionalContext transport gate only, no teacher quality claim',
              'status': 'incomplete', 'started_at_unix': time.time()}
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm/docker.sock'), timeout=1200)
    image = client.images.get(json.loads((ROOT / 'preflight/sdk_fixture_container.json').read_text())['image'])
    env = {item.split('=', 1)[0]: 'experiment-local' for item in image.attrs['Config']['Env']
           if any(word in item.split('=', 1)[0].upper() for word in
                  ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update({'ANTHROPIC_BASE_URL': 'http://127.0.0.1:4000', 'ANTHROPIC_AUTH_TOKEN': 'experiment-local',
                'ANTHROPIC_MODEL': 'gpt-6.1-terra', 'ANTHROPIC_SMALL_FAST_MODEL': 'gpt-6.1-terra',
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'IS_SANDBOX': '1', 'API_TIMEOUT_MS': '600000',
                'PYTHONDONTWRITEBYTECODE': '1', 'PROXY_MAX_TOKENS_CLAMP': '65536',
                'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'ALL_PROXY': '', 'http_proxy': '', 'https_proxy': '',
                'all_proxy': '', 'NO_PROXY': '*'})
    container = client.containers.run(image.id, name=NAME, entrypoint='', command=['tail', '-f', '/dev/null'],
        detach=True, mem_limit='128g', nano_cpus=8_000_000_000, privileged=True, environment=env,
        volumes={'/opt/hint-codex-runtime/python': {'bind': '/opt/python3.12-tmp', 'mode': 'ro'}})
    result['container'] = {'id': container.id, 'name': NAME, 'cpus': 8, 'memory': '128g'}
    try:
        print(json.dumps({'stage': 'setup', 'container': container.id}), flush=True)
        code, output = container.exec_run(['bash', '-c', 'rm -rf /app /root/.claude; mkdir -p /app /tmp/context_gate_out'])
        assert code == 0, output.decode()
        for local, remote in [(SOURCE / 'run_cc_sdk.py', '/tmp/sdk_script.py'),
                              (SOURCE / 'logging_utils.py', '/tmp/logging_utils.py'),
                              (SOURCE / 'litellm_proxy/claude_code_proxy.py', '/tmp/litellm_call_backs.py'),
                              (SOURCE / 'litellm_proxy/streaming_fix.py', '/tmp/streaming_fix.py')]:
            put_file(container, remote, local.read_bytes())
        put_file(container, '/tmp/context_probe.py', GUEST)
        put_file(container, '/tmp/query.json', json.dumps(PROMPT))
        put_file(container, '/app/evidence.txt', FILE_MARKER + '\n')
        put_file(container, '/tmp/config.yaml', render_proxy_config('openai', 'gpt-6.1-terra', 'experiment-local',
            'http://172.17.0.1:8765/sessions/' + SESSION + '/student/context_gate/v1', reasoning_effort='low', max_tokens=65536))
        code, output = container.exec_run(['bash', '-c', 'git init -q && git config user.email fixture@example.com && '
            'git config user.name Fixture && git add . && git commit -qm initial && git rev-parse HEAD'], workdir='/app')
        assert code == 0, output.decode()
        base = output.decode().strip()
        container.exec_run(['bash', '-c', 'PYTHONPATH=/tmp nohup /opt/python3.12-tmp/bin/litellm --config /tmp/config.yaml > /tmp/proxy.log 2>&1 &'])
        print(json.dumps({'stage': 'proxy_warmup'}), flush=True)
        code, output = container.exec_run(['bash', '-c', 'for i in $(seq 1 600); do curl -sf http://127.0.0.1:4000/health/liveliness >/dev/null && exit 0; sleep 1; done; exit 1'])
        assert code == 0, 'Fixture proxy did not become ready'
        print(json.dumps({'stage': 'real_sdk_query', 'session': SESSION}), flush=True)
        started = time.monotonic()
        code, output = container.exec_run(['timeout', '--signal=INT', '--kill-after=35', '240', PYTHON,
            '/tmp/context_probe.py', base], workdir='/app', environment=env)
        result['sdk_wall_seconds'] = time.monotonic() - started
        result['sdk_exit_code'] = code
        (OUT / 'stdout.log').write_bytes(output)
        for name in ('trajs.json', 'hook_events.json'):
            copy_file(container, '/tmp/context_gate_out/' + name, OUT / name)
        trajectory = json.loads((OUT / 'trajs.json').read_text())
        result['metadata'] = trajectory['metadata']
        result['bridge_status'] = status()
        assert code == 0 and trajectory['metadata']['status'] == 'completed'
        hooks = json.loads((OUT / 'hook_events.json').read_text())
        assert len(hooks) == 1 and hooks[0]['tool_name'] == 'Read' and hooks[0]['response_unchanged']
        assert hooks[0]['tool_response']['file']['content'] == FILE_MARKER + '\n'
        rows = save_records(result)
        requests = rows['model_requests.jsonl']
        responses = rows['model_responses.jsonl']
        result['context_occurrences_in_initial_request'] = occurrences(requests[0]['request']['messages'], CONTEXT_MARKER)
        result['context_occurrences_in_final_request'] = occurrences(requests[-1]['request']['messages'], CONTEXT_MARKER)
        tool_results = [message for message in requests[-1]['request']['messages']
                        if message.get('role') == 'tool' and message.get('tool_call_id') == hooks[0]['tool_use_id']]
        result['original_file_marker_occurrences_in_tool_result'] = occurrences(tool_results, FILE_MARKER)
        result['context_occurrences_in_tool_result'] = occurrences(tool_results, CONTEXT_MARKER)
        result['thread_ids'] = sorted({row['thread_id'] for row in responses})
        result['turn_ids'] = sorted({row['turn_id'] for row in responses})
        final = trajectory['metadata']['ResultMessage']['result']
        assert 'CONTEXT_GATE_COMPLETE' in final and final.count(CONTEXT_MARKER) == final.count(FILE_MARKER) == 1
        assert result['context_occurrences_in_initial_request'] == 0
        assert result['context_occurrences_in_final_request'] == 1
        assert result['original_file_marker_occurrences_in_tool_result'] == 1
        assert result['context_occurrences_in_tool_result'] == 0
        assert len(result['thread_ids']) == len(result['turn_ids']) == 1
        assert result['native_tool_event_count'] == 0 and not result['bridge_status']['stopped']
        code, output = container.exec_run(['git', 'diff', '--exit-code'], workdir='/app')
        assert code == 0, output.decode()
        result['status'] = 'passed'
    except BaseException as exc:
        result['error'] = str(exc) or type(exc).__name__
        raise
    finally:
        for name in ('proxy.log', 'sdk_script.log', 'system_prompt_config.json', 'system_prompt_actual.json'):
            try:
                copy_file(container, '/tmp/' + name, OUT / name)
            except docker.errors.NotFound:
                pass
        if 'native_tool_event_count' not in result:
            save_records(result)
        result['finished_at_unix'] = time.time()
        (OUT / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        container.stop(timeout=10)
        client.close()
        print(json.dumps({'status': result['status'], 'error': result.get('error'), 'result': str(OUT / 'result.json')}), flush=True)


if __name__ == '__main__':
    main()
