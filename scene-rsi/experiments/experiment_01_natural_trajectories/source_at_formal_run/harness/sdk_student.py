"""Scene entry point using the unchanged hintrsi SDK execution loop."""
import base64
from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time

import anyio

sys.path.insert(0, '/sdk')
import run_cc_sdk
from logging_utils import setup_logging


async def prompt_messages():
    image = base64.b64encode(Path('/app/reference.png').read_bytes()).decode()
    yield {'type': 'user', 'message': {'role': 'user', 'content': [
        {'type': 'text', 'text': Path('/inputs/prompt.txt').read_text()},
        {'type': 'image', 'source': {'type': 'base64', 'media_type': 'image/png', 'data': image}},
    ]}}


async def main():
    setup_logging('/capture/sdk_script.log')
    run_cc_sdk.SYSTEM_PROMPT_CONFIG_LOG_PATH = Path('/capture/system_prompt_config.json')
    options = run_cc_sdk.create_agent_options('/app')
    options.tools = ['Bash', 'Read', 'Write', 'Edit', 'Glob', 'Grep']
    options.setting_sources = []
    options.skills = []
    options.mcp_servers = {}
    options.strict_mcp_config = True
    options.max_turns = int(os.environ.get('SCENE_MAX_MODEL_CALLS', '120'))
    options.max_buffer_size = 64 * 1024 * 1024
    # The outer mount/PID/network namespace enforces access independently of prompts.
    options.sandbox = {'enabled': False}
    options.add_dirs = ['/capture']
    metadata = {}
    trajectories = {'main_agent': '', 'sub_agent': []}
    start = time.monotonic()
    try:
        await run_cc_sdk.run_agent_execution(prompt_messages(), '/app', options,
                                            commit_file='/capture/base_commit.txt',
                                            trajectories=trajectories, metadata=metadata)
        metadata['status'] = 'completed' if 'ResultMessage' in metadata and not metadata['ResultMessage'].get('is_error') else 'incomplete'
    except BaseException as error:
        metadata['status'] = 'incomplete'
        metadata['error'] = str(error) or type(error).__name__
        raise
    finally:
        metadata.update(wall_seconds=time.monotonic() - start, hint_enabled=False,
                        persistent_capability_enabled=False, online_teacher_enabled=False)
        Path('/capture/trajs.json').write_text(json.dumps({'trajectories': trajectories, 'metadata': metadata}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    subprocess.run(['git', 'init', '-q', '/app'], check=True)
    subprocess.run(['git', '-C', '/app', 'config', 'user.name', 'Scene experiment'], check=True)
    subprocess.run(['git', '-C', '/app', 'config', 'user.email', 'scene@local.invalid'], check=True)
    subprocess.run(['git', '-C', '/app', 'add', 'reference.png'], check=True)
    subprocess.run(['git', '-C', '/app', 'commit', '-qm', 'Initial image-only workspace'], check=True)
    tunnel = subprocess.Popen(['/opt/python/bin/python3.12', '/harness/socket_tunnel.py', '/model/proxy.sock'])
    time.sleep(.2)
    try:
        anyio.run(main)
    finally:
        tunnel.terminate()
        tunnel.wait()
