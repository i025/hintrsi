"""Resume three existing experiment overlays without recreating disks or runtimes."""
import json
import os
import socket
import subprocess
import time
from pathlib import Path

import docker

OUT = Path(__file__).with_name('ROOT.txt').read_text().strip()
OUT = Path(OUT)
ORIGINAL = Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
saved = OUT / 'config/runtime_resume.json'
record = json.loads(saved.read_text()) if saved.exists() else {'started_at': time.time(), 'lanes': []}
runtime = OUT / 'runtime'
runtime.mkdir(exist_ok=True)
socket_root = Path('/tmp/tcrsi-followup-20261126-182329')
socket_root.mkdir(exist_ok=True)

def save():
    (OUT / 'config/runtime_resume.json').write_text(json.dumps(record, indent=2) + '\n')

for lane in (0, 1, 2):
    original = ORIGINAL / ('vm' if lane == 0 else f'vm-lane{lane}')
    previous = json.loads((original / 'vm-state.json').read_text())
    port = previous['ssh_port']
    existing = next((r for r in record['lanes'] if r['lane'] == lane), None)
    owned_vm = existing and Path(f"/proc/{existing['vm_pid']}/cmdline").exists() and str(OUT).encode() in Path(f"/proc/{existing['vm_pid']}/cmdline").read_bytes()
    if existing and existing.get('status') == 'ready' and owned_vm:
        continue
    with socket.socket() as connection:
        if connection.connect_ex(('127.0.0.1', port)) == 0 and not owned_vm:
            raise RuntimeError(f'Lane {lane} SSH port is occupied; do not take it over')
    directory = runtime / f'lane{lane}'
    directory.mkdir(exist_ok=True)
    sockets = socket_root / f'lane{lane}'
    sockets.mkdir(exist_ok=True)
    command = previous['args'][:]
    command[command.index('-qmp') + 1] = f'unix:{sockets}/qmp.sock,server,nowait'
    command[command.index('-serial') + 1] = f'file:{directory}/console.log'
    command[command.index('-debugcon') + 1] = f'file:{directory}/bios.log'
    environment = dict(os.environ)
    environment.pop('LD_LIBRARY_PATH', None)
    if owned_vm:
        row = existing
    else:
        with (directory / 'qemu_resume_02.log').open('xb') as log:
            vm = subprocess.Popen(['nice', '-n', '10'] + command, env=environment,
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        row = {'lane': lane, 'vm_pid': vm.pid, 'vm_command': command,
            'overlay': previous['overlay'], 'status': 'booting', 'ssh_port': port}
        record['lanes'] = [r for r in record['lanes'] if r['lane'] != lane] + [row]
    save()
    ssh = ['ssh', '-F', '/dev/null', '-p', str(port), '-i',
        '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/vm/ssh_key',
        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=5',
        '-o', f'UserKnownHostsFile={original}/known_hosts', '-o', 'StrictHostKeyChecking=yes']
    for attempt in range(90):
        if not Path(f"/proc/{row['vm_pid']}/cmdline").exists():
            raise RuntimeError(f'Lane {lane} QEMU exited')
        try:
            result = subprocess.run(ssh + ['experiment@127.0.0.1', 'true'],
                capture_output=True, timeout=15)
        except subprocess.TimeoutExpired:
            time.sleep(3)
            continue
        if result.returncode == 0:
            break
        if attempt % 6 == 0:
            print(json.dumps({'lane': lane, 'status': 'waiting_for_ssh', 'attempt': attempt}), flush=True)
        time.sleep(3)
    else:
        raise RuntimeError(f'Lane {lane} did not become reachable')
    subprocess.run(ssh + ['experiment@127.0.0.1', 'sudo systemctl start hint-docker'],
        capture_output=True, check=True, timeout=60)
    docker_socket = sockets / 'docker.sock'
    tunnel = ssh + ['-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=15',
        '-o', 'ServerAliveCountMax=3', '-M', '-S', str(sockets / 'ssh-control.sock'),
        '-N', '-L', f'{docker_socket}:/var/run/docker.sock',
        '-R', '0.0.0.0:8765:127.0.0.1:8765', '-R', '0.0.0.0:8766:127.0.0.1:8766',
        'experiment@127.0.0.1']
    with (directory / 'ssh-tunnel.log').open('xb') as log:
        process = subprocess.Popen(tunnel, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log, start_new_session=True)
    row.update(tunnel_pid=process.pid, tunnel_command=tunnel,
        docker_host='unix://' + str(docker_socket))
    save()
    client = docker.DockerClient(base_url=row['docker_host'], version='1.57', timeout=20)
    try:
        for attempt in range(30):
            try:
                client.ping()
                break
            except Exception:
                time.sleep(2)
        else:
            raise RuntimeError(f'Lane {lane} Docker tunnel failed')
        row.update(status='ready', containers=[{'name': c.name, 'labels': c.labels}
            for c in client.containers.list()], images=[{'tags': i.tags, 'size': i.attrs['Size']}
            for i in client.images.list()], ready_at=time.time())
    finally:
        client.close()
    save()
    print(json.dumps({'lane': lane, 'status': row['status'], 'images': len(row['images']),
        'existing_containers': len(row['containers'])}), flush=True)
record.update(status='ready', finished_at=time.time())
save()
