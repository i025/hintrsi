"""Filesystem and network isolation for the shared SDK; contains no scene strategy."""
from pathlib import Path
import json
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
BWRAP = Path('/srv/lab-disks/disk2/users/xymo/.local/share/codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl/codex-resources/bwrap')
BLENDER = Path('/srv/lab-disks/disk2/users/xymo/environments/image-to-3d-harness/opt/blender-5.2.2-linux-x64')
PYTHON = Path('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/python/cpython-3.12.16-linux-x86_64-gnu')
ENVIRONMENT = Path('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env')


def prepare(directory, image, prompt, checkpoint=None, session=None):
    directory = Path(directory).resolve()
    for name in ('workspace', 'home', 'capture', 'tmp', 'inputs'):
        (directory / name).mkdir(parents=True, exist_ok=True)
    if checkpoint:
        shutil.copytree(checkpoint, directory / 'workspace', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    shutil.copyfile(image, directory / 'workspace/reference.png')
    (directory / 'inputs/prompt.txt').write_text(prompt)
    (directory / 'inputs/session.json').write_text(json.dumps(session or {}, indent=2))
    images = [{'path': '/app/reference.png', 'label': 'Reference image'}]
    if checkpoint:
        images.append({'path': '/app/final.png', 'label': 'Current reconstruction image'})
    images += (session or {}).get('additional_images', [])
    (directory / 'inputs/images.json').write_text(json.dumps(images, indent=2))
    return directory


def command(directory, proxy_socket, model_calls=120):
    directory = Path(directory).resolve()
    args = [str(BWRAP), '--unshare-all', '--die-with-parent', '--new-session', '--clearenv',
            '--ro-bind', '/usr', '/usr', '--ro-bind', '/bin', '/bin', '--ro-bind', '/lib', '/lib',
            '--ro-bind', '/lib64', '/lib64', '--ro-bind', '/etc', '/etc', '--proc', '/proc',
            '--dev', '/dev', '--tmpfs', '/dev/shm',
            '--bind', str(directory / 'workspace'), '/app',
            '--bind', str(directory / 'home'), '/home/student',
            '--bind', str(directory / 'capture'), '/capture',
            '--bind', str(directory / 'tmp'), '/tmp',
            '--ro-bind', str(directory / 'inputs'), '/inputs',
            '--ro-bind', str(ROOT / 'sdk'), '/sdk', '--ro-bind', str(ROOT / 'harness'), '/harness',
            '--ro-bind', str(BLENDER), '/opt/blender', '--ro-bind', str(PYTHON), '/opt/python',
            '--ro-bind', str(ENVIRONMENT), '/opt/venv',
            '--dir', '/runtime/bin', '--ro-bind', str(ROOT / 'harness/blender.py'), '/runtime/bin/blender',
            '--dir', '/model', '--ro-bind', str(proxy_socket), '/model/proxy.sock', '--chdir', '/app']
    env = {'HOME': '/home/student', 'USER': 'student', 'PATH': '/runtime/bin:/opt/python/bin:/usr/bin:/bin',
           'PYTHONPATH': '/sdk:/sdk/litellm_proxy:/opt/venv/lib/python3.12/site-packages',
           'PYTHONDONTWRITEBYTECODE': '1', 'LANG': 'C.UTF-8', 'TERM': 'dumb',
           'ANTHROPIC_BASE_URL': 'http://127.0.0.1:18767', 'ANTHROPIC_API_KEY': 'local-scene',
           'ANTHROPIC_MODEL': 'default_model', 'ANTHROPIC_DEFAULT_HAIKU_MODEL': 'default_model',
           'ANTHROPIC_DEFAULT_SONNET_MODEL': 'default_model', 'ANTHROPIC_DEFAULT_OPUS_MODEL': 'default_model',
           'CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC': '1', 'CLAUDE_CONFIG_DIR': '/home/student/.claude',
           'CLAUDE_CODE_DISABLE_AUTO_MEMORY': '1',
           'BUN_JSC_useJIT': '0', 'ENABLE_TOOL_SEARCH': 'false',
           'SCENE_WORKSPACE': '/app', 'SCENE_MAX_MODEL_CALLS': str(model_calls),
           'OMP_NUM_THREADS': '8', 'OPENBLAS_NUM_THREADS': '1', 'CUDA_VISIBLE_DEVICES': '',
           'LIBGL_ALWAYS_SOFTWARE': '1', 'EGL_PLATFORM': 'surfaceless', 'GALLIUM_DRIVER': 'llvmpipe'}
    for key, value in env.items():
        args += ['--setenv', key, value]
    return args + ['--', '/opt/python/bin/python3.12', '/harness/sdk_student.py']
