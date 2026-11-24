#!/usr/bin/env python3
"""Record the six prepared runtimes without starting workers or model turns."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import docker

from check_lanes import ROWS, TASKS
from prepare_lane import OLD, OUT, ROOT


def load(path):
    return json.loads(path.read_text())


def main_lane():
    client = docker.DockerClient(base_url='unix://' + str(ROOT/'vm/docker.sock'), timeout=30)
    try:
        info = client.info()
        images = []
        for task in TASKS[0]:
            image = client.images.get(ROWS[task]['image_name'])
            images.append({'task':task,'original_alias':ROWS[task]['image_name'],
                           'ready':True,'image_id':image.id})
        record = {'lane':0,'ready':True,'assigned_images':images,
                  'resources':{key:info[key] for key in
                      ('NCPU','MemTotal','Driver','CgroupVersion','KernelVersion')},
                  'docker_version':client.version()['Version'],
                  'runtime':{'python':'3.12.16','sdk':'0.2.186','litellm':'1.81.8',
                             'cli_version':'2.1.329 (Claude Code)'},
                  'runtime_evidence':str(ROOT/'preflight/sdk_sigsegv_diagnosis/summary.json'),
                  'gateway_evidence':str(ROOT/'preflight/formal_04_service_restart/result.json'),
                  'inspection':'Docker info and two assigned image metadata only; no active container execution.'}
        (OUT/'lane0_ready.json').write_text(json.dumps(record,indent=2)+'\n')
        return record
    finally:
        client.close()


def build():
    rows = [main_lane()]
    rows.extend(load(OUT/f'lane{lane}_ready.json') for lane in range(1,6))
    assert all(row['ready'] for row in rows)
    lanes = []
    for row in rows:
        lane = row['lane']
        directory = ROOT/('vm' if lane == 0 else f'vm-lane{lane}')
        state = load(directory/'vm-state.json')
        tunnel = load(directory/'ssh-tunnel-state.json')
        assert state['vcpus'] == 8 and state['memory_mb'] == 147456
        assert state['qemu_version'].startswith('8.2.2 ')
        assert state['machine'] == 'pc-q35-4.2'
        assert state['acceleration'] == 'tcg,thread=multi'
        assert Path(f"/proc/{state['pid']}").exists()
        assert Path(f"/proc/{tunnel['pid']}").exists()
        args = state['args']
        observed = row if lane == 0 else load(OUT/f'lane{lane}.json')
        nice = os.getpriority(os.PRIO_PROCESS, state['pid'])
        assert nice == 10
        assert args[args.index('-cpu')+1] == 'Nehalem'
        backing = OLD/'vm-cpu-probe/guest.qcow2'
        backing_fds = []
        for entry in Path(f"/proc/{state['pid']}/fd").iterdir():
            try:
                if entry.resolve() != backing:
                    continue
                flags = (Path(f"/proc/{state['pid']}/fdinfo")/entry.name).read_text()
                access = int(next(line.split(':',1)[1].strip()
                                 for line in flags.splitlines() if line.startswith('flags:')),8) & 3
                backing_fds.append({'fd':entry.name,'access_mode':access})
            except FileNotFoundError:
                pass
        assert backing_fds and all(item['access_mode'] == 0 for item in backing_fds)
        lanes.append({'lane':lane,'docker_host':'unix://' + str(directory/'docker.sock'),
            'ssh_port':state['ssh_port'],'vm_pid':state['pid'],'tunnel_pid':tunnel['pid'],
            'ready':True,'tasks':TASKS[lane],'process_nice':nice,
            'observed_resources':observed['resources'],
            'docker_version':observed['docker_version'],
            'resources':{'vcpus':8,'guest_memory_mib':147456,
                         'container_cpus':8,'container_memory_bytes':137438953472},
            'qemu':{'version':state['qemu_version'],'cpu':'Nehalem',
                    'machine':state['machine'],'acceleration':state['acceleration'],
                    'binary':args[0],'bios':args[args.index('-bios')+1],
                    'kernel':args[args.index('-kernel')+1],
                    'initrd':args[args.index('-initrd')+1]},
            'immutable_backing':str(backing),'backing_readonly_fds':backing_fds,
            'runtime':row['runtime'],'runtime_guest_path':'/opt/hint-codex-runtime/python',
            'runtime_container_path':'/opt/python3.12-tmp','runtime_mount':'ro',
            'gateway':{'address':'172.17.0.1','bridge_port':8765,'progress_port':8766},
            'assigned_images':row['assigned_images'],
            'gate':str(OUT/f'lane{lane}_ready.json'),
            'vm_state':str(directory/'vm-state.json'),
            'tunnel_state':str(directory/'ssh-tunnel-state.json')})
    now = datetime.now(timezone.utc).isoformat()
    record = {'created_at_utc':now,'ready':True,'lanes':lanes,
              'scope':'Runtime preparation only; no new formal workers or real model probes.',
              'real_model_calls':0,'prepared_vm_count':5,'total_vm_count':6,
              'total_configured_vcpus':48,'total_configured_guest_memory_gib':864,
              'max_heavy_preparations':2,
              'shared_runtime_bundle':str(OUT/'runtime_bundle.json'),
              'offline_sdk_gate':str(OUT/'lane1_sdk_gate/host_result.json'),
              'source_vm_unchanged':True,
              'active_source_overlay_used_as_backing':False,
              'main_vm_image_export_performed':False}
    (OUT/'runtime_manifest.json').write_text(json.dumps(record,indent=2)+'\n')
    purposes = {
        'prepare_lane.py':'Create new overlays, boot identical VMs, connect isolated tunnels, and copy runtime.',
        'prepare_remaining.py':'Limit remaining new-VM preparation to two concurrent operations.',
        'probe_lane.py':'Run the single network-none real SDK tool/resume fixture with fake API.',
        'check_lanes.py':'Pull only missing assigned images and check fixed versions, resources, and gateways.',
        'build_manifest.py':'Record the final runtime manifest from completed gates and read-only process metadata.',
        'run_lane_checks.py':'Run version and gateway checks sequentially while one image extraction remains active.',
    }
    inventory = {'created_at_utc':now,'files':[{'path':str(OUT/name),'bytes':(OUT/name).stat().st_size,
                   'purpose':purpose} for name,purpose in purposes.items()],
                 'production_source_modified':False,'real_model_calls':0}
    (OUT/'helper_inventory.json').write_text(json.dumps(inventory,indent=2)+'\n')
    print(json.dumps({'ready':True,'manifest':str(OUT/'runtime_manifest.json'),
                      'helper_inventory':str(OUT/'helper_inventory.json')}),flush=True)


if __name__ == '__main__':
    build()
