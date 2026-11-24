#!/usr/bin/env python3
"""Prepare an independent VM lane using the unchanged experiment runtime."""

import argparse
import io
import json
import os
import shlex
import subprocess
import tarfile
import time
from pathlib import Path

import docker
import requests

ROOT = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
OLD = ROOT.parent / 'hint-baseline-run'
OUT = ROOT / 'preflight/parallel_runtime'
BASE = OLD / 'vm-cpu-probe/guest.qcow2'
QEMU_IMG = ROOT / 'vm/runtime-noble/bin/qemu-img'
PYTHON = '/opt/python3.12-tmp/bin/python3'


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def announce(lane, stage, **values):
    print(json.dumps({'lane': lane, 'stage': stage, 'at_unix': time.time(), **values}), flush=True)


def ssh_args(lane):
    directory = ROOT / f'vm-lane{lane}'
    return ['ssh', '-F', '/dev/null', '-S', str(directory / 'ssh-control.sock'), '-p', str(22230 + lane),
            '-i', str(OLD / 'vm/ssh_key'), '-o', 'IdentitiesOnly=yes',
            '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
            '-o', 'UserKnownHostsFile=' + str(directory / 'known_hosts'),
            '-o', 'StrictHostKeyChecking=yes', 'experiment@127.0.0.1']


def ssh(lane, command, **kwargs):
    return subprocess.run(ssh_args(lane) + [command], check=True, **kwargs)


def start(lane):
    directory = ROOT / f'vm-lane{lane}'
    directory.mkdir()
    known = (ROOT / 'vm/known_hosts').read_text().replace(
        '[127.0.0.1]:22230', f'[127.0.0.1]:{22230 + lane}')
    (directory / 'known_hosts').write_text(known)
    os.chmod(directory / 'known_hosts', 0o600)
    subprocess.run([str(QEMU_IMG), 'create', '-f', 'qcow2', '-F', 'qcow2',
                    '-b', str(BASE), str(directory / 'guest.qcow2')], check=True)
    state = json.loads((ROOT / 'vm/vm-state.json').read_text())
    args = state['args'][:]
    for index, value in enumerate(args):
        if value.startswith('file=' + str(ROOT / 'vm/guest.qcow2')):
            args[index] = value.replace(str(ROOT / 'vm/guest.qcow2'), str(directory / 'guest.qcow2'))
    args[args.index('-netdev') + 1] = f'user,id=net0,hostfwd=tcp:127.0.0.1:{22230 + lane}-:22'
    args[args.index('-serial') + 1] = 'file:' + str(directory / 'console.log')
    args[args.index('-debugcon') + 1] = 'file:' + str(directory / 'bios-debug.log')
    args[args.index('-qmp') + 1] = 'unix:' + str(directory / 'qmp.sock') + ',server,nowait'
    assert args[args.index('-smp') + 1] == '8,sockets=1,cores=8,threads=1'
    assert args[args.index('-m') + 1] == '147456'
    env = dict(os.environ)
    env.pop('LD_LIBRARY_PATH', None)
    with (directory / 'qemu.log').open('ab') as log:
        proc = subprocess.Popen(['nice', '-n', '10'] + args, env=env,
            stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    record = {**state, 'pid': proc.pid, 'args': args, 'lane': lane,
        'ssh_port': 22230 + lane, 'overlay': str(directory / 'guest.qcow2'),
        'backing': str(BASE), 'started_at_unix': time.time(), 'model_calls': 0}
    save(directory / 'vm-state.json', record)
    announce(lane, 'vm_started', pid=proc.pid)
    for attempt in range(30):
        result = subprocess.run(ssh_args(lane) + ['true'], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=25)
        if result.returncode == 0:
            break
        announce(lane, 'ssh_wait', attempt=attempt + 1,
                 message=result.stderr.decode(errors='replace').strip()[-300:])
        time.sleep(5)
    else:
        raise RuntimeError('The new lane did not become reachable')
    configure_guest(lane)
    connect(lane)
    inspect(lane)


def configure_guest(lane):
    program = ("from pathlib import Path;import subprocess;"
        "Path('/etc/ssh/sshd_config.d/00-hint-codex-lane.conf').write_text('GatewayPorts clientspecified\\n');"
        "subprocess.run(['/usr/sbin/sshd','-t'],check=True);"
        "subprocess.run(['systemctl','reload','ssh'],check=True);"
        "subprocess.run(['systemctl','start','hint-docker'],check=True)")
    ssh(lane, 'sudo python3 -c ' + shlex.quote(program))
    announce(lane, 'existing_docker_service_started', gateway_ports='clientspecified')


def connect(lane):
    directory = ROOT / f'vm-lane{lane}'
    template = json.loads((ROOT / 'vm/ssh-tunnel-state.json').read_text())['args']
    tunnel = [value.replace(str(ROOT / 'vm'), str(directory)).replace('22230', str(22230 + lane))
              for value in template]
    with (directory / 'ssh-tunnel.log').open('ab') as log:
        proc = subprocess.Popen(tunnel, stdin=subprocess.DEVNULL, stdout=log,
                                stderr=log, start_new_session=True)
    save(directory / 'ssh-tunnel-state.json', {'pid': proc.pid, 'args': tunnel,
        'started_at_unix': time.time(), 'docker_host': 'unix://' + str(directory / 'docker.sock')})
    for attempt in range(30):
        client = docker.DockerClient(base_url='unix://' + str(directory / 'docker.sock'), version='1.57', timeout=10)
        try:
            client.ping()
            break
        except (docker.errors.DockerException, requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout):
            time.sleep(2)
        finally:
            client.close()
    else:
        raise RuntimeError('The new lane Docker socket did not become reachable')


def inspect(lane):
    directory = ROOT / f'vm-lane{lane}'
    client = docker.DockerClient(base_url='unix://' + str(directory / 'docker.sock'), timeout=30)
    info = client.info()
    program = "import json,os,platform;from pathlib import Path;print(json.dumps({'kernel':platform.release(),'cpus':os.cpu_count(),'runtime_exists':Path('/opt/hint-codex-runtime/python/bin/python3').exists()}))"
    profile = json.loads(ssh(lane, 'python3 -c ' + shlex.quote(program), capture_output=True, text=True).stdout)
    pid = json.loads((directory / 'vm-state.json').read_text())['pid']
    backing_fds = []
    for fd in Path(f'/proc/{pid}/fd').iterdir():
        try:
            target = os.readlink(fd)
        except FileNotFoundError:
            continue
        if target == str(BASE):
            flags = next(line.split()[1] for line in Path(f'/proc/{pid}/fdinfo/{fd.name}').read_text().splitlines() if line.startswith('flags:'))
            backing_fds.append({'fd': fd.name, 'access_mode': int(flags, 8) & 3})
    assert backing_fds and all(row['access_mode'] == 0 for row in backing_fds)
    record = {'lane': lane, 'stage': 'booted', 'model_calls': 0, 'profile': profile,
        'resources': {key: info.get(key) for key in ['NCPU', 'MemTotal', 'Driver', 'CgroupVersion', 'KernelVersion']},
        'docker_version': client.version()['Version'], 'backing_fds': backing_fds,
        'bridge_network': client.networks.get('bridge').attrs['IPAM']['Config'],
        'images': [{'id': image.id, 'tags': image.tags} for image in client.images.list()]}
    save(directory / 'runtime.json', record)
    save(OUT / f'lane{lane}.json', record)
    client.close()
    announce(lane, 'boot_verified', profile=profile, resources=record['resources'],
             image_count=len(record['images']), backing_readonly=True)


def pack_runtime():
    started = time.monotonic()
    path = OUT / 'python-runtime.tar.gz'
    def source_filter(info):
        return None if '__pycache__' in Path(info.name).parts else info
    with tarfile.open(path, 'w:gz', compresslevel=1) as archive:
        archive.add(OLD / 'python/cpython-3.12.16-linux-x86_64-gnu', arcname='python', filter=source_filter)
        archive.add(OLD / 'env/lib/python3.12/site-packages', arcname='python/lib/python3.12/site-packages', filter=source_filter)
        for name, body in {'litellm':'from litellm import run_server\nrun_server()\n',
                           'pip3':'from pip._internal.cli.main import main\nraise SystemExit(main())\n'}.items():
            content = ('#!/opt/python3.12-tmp/bin/python3\n' + body).encode()
            info = tarfile.TarInfo('python/bin/' + name)
            info.mode, info.size = 0o755, len(content)
            archive.addfile(info, io.BytesIO(content))
    save(OUT / 'runtime_bundle.json', {'archive': str(path), 'bytes': path.stat().st_size,
        'source': 'Existing unchanged standalone Python and installed site-packages; same original prepare_runtime recipe',
        'elapsed_seconds': time.monotonic() - started, 'model_calls': 0})
    print(json.dumps({'stage': 'runtime_packed', 'bytes': path.stat().st_size}), flush=True)


def install_runtime(lane):
    started = time.monotonic()
    ssh(lane, 'sudo mkdir -p /opt/hint-codex-runtime')
    with (OUT / 'python-runtime.tar.gz').open('rb') as content:
        ssh(lane, 'sudo tar -xzf - -C /opt/hint-codex-runtime', stdin=content)
    announce(lane, 'runtime_copied', elapsed_seconds=time.monotonic() - started)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['start', 'inspect', 'pack-runtime', 'install-runtime', 'configure-guest', 'connect'])
    parser.add_argument('--lane', type=int)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.action == 'pack-runtime':
        pack_runtime()
    else:
        {'start': start, 'inspect': inspect, 'install-runtime': install_runtime,
         'configure-guest': configure_guest, 'connect': connect}[args.action](args.lane)
