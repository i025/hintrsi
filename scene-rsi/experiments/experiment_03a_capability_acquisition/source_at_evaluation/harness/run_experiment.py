"""Interleave independent tasks across two identical CPU workers."""
from pathlib import Path
import json
import os
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/experiment_01_natural_trajectories'
PYTHON = '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
DEADLINE = 1795803968  # 2026-11-27 18:26:08 UTC; includes preparation and analysis.


def main():
    scenes = json.loads((ROOT / 'configs/scenes.json').read_text())['scenes']
    queue = [(scene, repetition) for repetition in range(1, 4) for scene in scenes]
    active = {}
    completed = []
    started = time.time()
    stop = False

    def interrupt(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGINT, interrupt)
    try:
        while queue or active:
            for lane, (process, run_id, output) in list(active.items()):
                if process.poll() is not None:
                    completed.append({'run': run_id, 'exit_code': process.returncode, 'finished_at': time.time()})
                    output.close()
                    del active[lane]
                    print(json.dumps(completed[-1]), flush=True)
            if time.time() >= DEADLINE - 3600 or (EXPERIMENT / 'STOP').exists():
                stop = True  # Keep at least one hour for analysis and final delivery.
            if stop:
                break
            for lane in range(2):
                if lane in active or not queue:
                    continue
                scene, repetition = queue.pop(0)
                run_id = scene['id'] + '-R' + str(repetition)
                directory = EXPERIMENT / 'runs' / run_id
                directory.mkdir(parents=True)
                argv = [PYTHON, '-u', '-B', str(ROOT / 'harness/run_sdk_session.py'),
                        '--directory', str(directory), '--image', scene['reference'],
                        '--prompt', str(ROOT / 'configs/formal_prompt.txt'), '--seconds', '1500',
                        '--calls', '120', '--port', str(18865 + lane),
                        '--cpus', ','.join(str(cpu) for cpu in range(32 + lane * 8, 40 + lane * 8))]
                output = (directory / 'supervisor.log').open('wb')
                process = subprocess.Popen(argv, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
                active[lane] = (process, run_id, output)
                print(json.dumps({'launched': run_id, 'lane': lane, 'timestamp': time.time()}), flush=True)
            summary = {'started_at': started, 'updated_at': time.time(),
                       'active': [value[1] for value in active.values()],
                       'queued': [scene['id'] + '-R' + str(rep) for scene, rep in queue],
                       'completed': completed, 'student_seconds': 1500, 'model_requests': 120,
                       'concurrency': 2, 'cpu_threads_each': 8, 'all_students_finished': not queue and not active}
            (EXPERIMENT / 'batch_status.json').write_text(json.dumps(summary, indent=2))
            time.sleep(2)
    finally:
        for process, run_id, output in active.values():
            process.terminate()
        for process, run_id, output in active.values():
            process.wait()
            output.close()
        (EXPERIMENT / 'batch_finished.json').write_text(json.dumps({
            'finished_at': time.time(), 'seconds': time.time() - started,
            'completed': completed, 'unstarted': len(queue), 'interrupted': stop,
            'owned_supervisors_stopped': True}, indent=2))


if __name__ == '__main__':
    main()
