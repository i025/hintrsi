"""Fresh filesystem for one native Codex CLI session; no reconstruction logic."""
from pathlib import Path
import json
import os
import shutil

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = Path('/srv/lab-disks/disk2/users/xymo/.local/share/codex/packages/standalone/releases/0.163.0-x86_64-unknown-linux-musl')
BWRAP = PACKAGE / 'codex-resources/bwrap'
BLENDER = Path('/srv/lab-disks/disk2/users/xymo/environments/image-to-3d-harness/opt/blender-5.2.2-linux-x64')
DISABLED = ['apps', 'plugins', 'remote_plugin', 'recommended_plugins', 'memories', 'multi_agent',
            'multi_agent_v2', 'skill_search', 'skill_mcp_dependency_install', 'shell_snapshot',
            'browser_use', 'browser_use_external', 'in_app_browser', 'computer_use',
            'image_generation', 'standalone_web_search', 'goals', 'external_agent_memory_import']


def prepare(directory, image=None):
    directory = Path(directory)
    for name in ('workspace', 'home/.codex', 'capture', 'tmp'):
        (directory / name).mkdir(parents=True, exist_ok=True)
    auth = directory / 'home/.codex/auth.json'
    if not auth.exists():
        shutil.copyfile(Path.home() / '.codex/auth.json', auth)
        auth.chmod(0o600)
    if image:
        shutil.copyfile(image, directory / 'workspace/reference.png')
    return directory


def base_command(directory):
    directory = Path(directory).resolve()
    args = [str(BWRAP), '--unshare-all', '--share-net', '--die-with-parent', '--new-session',
            '--clearenv', '--ro-bind', '/usr', '/usr', '--ro-bind', '/bin', '/bin',
            '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
            '--ro-bind', '/etc', '/etc', '--proc', '/proc', '--dev', '/dev',
            '--dir', '/home/student', '--bind', str(directory / 'home'), '/home/student',
            '--bind', str(directory / 'workspace'), '/work',
            '--bind', str(directory / 'capture'), '/capture',
            '--bind', str(directory / 'tmp'), '/tmp',
            '--ro-bind', str(PACKAGE), '/opt/codex',
            '--ro-bind', str(BLENDER), '/opt/blender',
            '--dir', '/runtime/bin', '--ro-bind', str(ROOT / 'harness/blender.py'), '/runtime/bin/blender',
            '--chdir', '/work']
    env = {'HOME': '/home/student', 'USER': 'student', 'CODEX_HOME': '/home/student/.codex',
           'PATH': '/runtime/bin:/opt/codex:/usr/bin:/bin', 'LANG': 'C.UTF-8', 'TERM': 'dumb',
           'OMP_NUM_THREADS': '8', 'OPENBLAS_NUM_THREADS': '1', 'CUDA_VISIBLE_DEVICES': '',
           'LIBGL_ALWAYS_SOFTWARE': '1', 'EGL_PLATFORM': 'surfaceless', 'GALLIUM_DRIVER': 'llvmpipe',
           'RUST_LOG': 'codex_api=debug,codex_core::client=debug',
           'PYTHONDONTWRITEBYTECODE': '1'}
    for key in ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy'):
        if key in os.environ:
            env[key] = os.environ[key]
    for key, value in env.items():
        args += ['--setenv', key, value]
    return args


def codex_command(directory, image=True):
    args = base_command(directory) + ['--', '/opt/codex/codex', 'exec', '--json',
            '--ignore-user-config', '--skip-git-repo-check', '-m', 'gpt-6.1-terra',
            '-c', 'model_reasoning_effort="low"', '--sandbox', 'workspace-write',
            '-c', 'approval_policy="never"', '-c', 'web_search="disabled"',
            '-c', 'project_doc_max_bytes=0', '-c', 'mcp_servers={}',
            '-c', 'features.skip_host_skill_discovery=true',
            '-c', 'shell_environment_policy.inherit="all"',
            '--output-last-message', '/work/agent_final.txt']
    for feature in DISABLED:
        args += ['--disable', feature]
    if image:
        args += ['--image', '/work/reference.png']
    return args + ['-']
