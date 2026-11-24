#!/usr/bin/env python3
"""Run a separate offline H-context check without altering the stress cases."""

import json
import time

import docker
import pyarrow.parquet as pq

from host_stress import ROOT, OUT, PYTHON, put_file, collect


def main():
    row = next(item for item in pq.read_table(ROOT.parent / 'hint-baseline-run/data/deep_swe_tasks.parquet').to_pylist()
               if item['instance_id'] == 'anko-default-function-arguments')
    prompt = (ROOT / 'source/benchmark/deepswe/prompts/deep_swe_user_prompt.md').read_text().replace('{{issue_description}}', row['problem_statement'])
    hint = (ROOT / 'runs/codex_formal_02/codex_formal_02_shared/hint_gen/anko-default-function-arguments/hint_compact_r1.md').read_bytes()
    client = docker.DockerClient(base_url='unix://' + str(ROOT / 'vm/docker.sock'), timeout=300)
    image = client.images.get(row['image_name'])
    env = {item.split('=', 1)[0]: 'offline-fixture' for item in image.attrs['Config'].get('Env', [])
           if any(word in item.split('=', 1)[0].upper() for word in
                  ('KEY', 'TOKEN', 'SECRET', 'PASSWORD', 'ANTHROPIC', 'OPENAI', 'OFOX', 'HUBROUTER'))}
    env.update({'ANTHROPIC_BASE_URL': 'http://127.0.0.1:8767', 'ANTHROPIC_AUTH_TOKEN': 'offline-fixture',
                'ANTHROPIC_MODEL': 'gpt-6.1-terra', 'ANTHROPIC_SMALL_FAST_MODEL': 'gpt-6.1-terra',
                'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'IS_SANDBOX': '1',
                'API_TIMEOUT_MS': '60000', 'PYTHONDONTWRITEBYTECODE': '1',
                'HTTP_PROXY': '', 'HTTPS_PROXY': '', 'ALL_PROXY': '', 'http_proxy': '',
                'https_proxy': '', 'all_proxy': '', 'NO_PROXY': '*', 'SYSTEM_PROMPT_FILE': '',
                'APPEND_SYSTEM_PROMPT_FILE': '/tmp/hint.txt'})
    container = client.containers.run(image.id, name='codex-sdk-jit-env-offline', entrypoint='',
        command=['tail', '-f', '/dev/null'], detach=True, mem_limit='128g', nano_cpus=8_000_000_000,
        privileged=True, network_mode='none', environment=env,
        volumes={'/opt/hint-codex-runtime/python': {'bind': '/opt/python3.12-tmp', 'mode': 'ro'}})
    result = {'container': container.id, 'real_model_calls': 0, 'network': 'none', 'started_at_unix': time.time(),
              'cpus': 8, 'memory': '128g', 'project_source_preserved': True, 'exact_h_prompt': True}
    try:
        code, before = container.exec_run(['git', 'status', '--porcelain'], workdir='/app')
        assert code == 0
        for local, remote in [(ROOT / 'source/run_cc_sdk.py', '/tmp/sdk_script.py'),
                              (ROOT / 'source/logging_utils.py', '/tmp/logging_utils.py'),
                              (ROOT / 'preflight/sdk_hook_fixture/probe.py', '/tmp/hook_fixture.py'),
                              (OUT / 'guest_env_probe.py', '/tmp/guest_env_probe.py')]:
            put_file(container, remote, local.read_bytes())
        put_file(container, '/tmp/env_original_prompt.txt', prompt)
        put_file(container, '/tmp/hint.txt', hint)
        started = time.monotonic()
        code, output = container.exec_run(['timeout', '--signal=INT', '--kill-after=20', '230', PYTHON,
                                           '/tmp/guest_env_probe.py'], workdir='/app')
        result.update({'exit_code': code, 'host_exec_seconds': time.monotonic() - started})
        collect(container, '/tmp/env_probe_out', OUT / 'environment_propagation')
        (OUT / 'environment_propagation/stdout.log').write_bytes(output)
        result.update(json.loads((OUT / 'environment_propagation/result.json').read_text()))
        after_code, after = container.exec_run(['git', 'status', '--porcelain'], workdir='/app')
        result['source_status_unchanged'] = code == 0 and after_code == 0 and before == after
        assert result['passed'] and result['source_status_unchanged']
    finally:
        container.stop(timeout=10)
        container.reload()
        result['container_running_after_cleanup'] = container.attrs['State']['Running']
        result['finished_at_unix'] = time.time()
        (OUT / 'environment_propagation_host.json').write_text(json.dumps(result, indent=2) + '\n')
        client.close()
        print(json.dumps(result))


if __name__ == '__main__':
    main()
