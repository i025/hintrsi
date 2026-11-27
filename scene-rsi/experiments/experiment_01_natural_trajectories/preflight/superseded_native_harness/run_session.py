from pathlib import Path
import argparse
import json
import os
import resource
import signal
import subprocess
import time

from isolation import ROOT, prepare, codex_command


def execute(directory, prompt, image=None, seconds=1500, cpus=None):
    directory = prepare(directory, image)
    (directory / 'prompt.txt').write_text(prompt)
    argv = codex_command(directory, image is not None)
    (directory / 'argv.json').write_text(json.dumps(argv, indent=2))
    start = time.time()

    def limits():
        os.nice(15)
        if cpus:
            os.sched_setaffinity(0, cpus)
        resource.setrlimit(resource.RLIMIT_AS, (32 * 1024 ** 3, 32 * 1024 ** 3))

    with (directory / 'events.jsonl').open('w') as output, (directory / 'stderr.log').open('w') as errors:
        process = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=output, stderr=errors,
                                   text=True, start_new_session=True, preexec_fn=limits)
        process.stdin.write(prompt)
        process.stdin.close()
        (directory / 'status.json').write_text(json.dumps({'status': 'running', 'pid': process.pid,
                                                          'started_at': start, 'seconds_limit': seconds}, indent=2))
        stopped = None
        while process.poll() is None:
            if time.time() - start >= seconds:
                stopped = 'wall_time_limit'
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                break
            time.sleep(2)
        returncode = process.wait()
    state = {'status': 'completed' if returncode == 0 else 'failed', 'exit_code': returncode,
             'started_at': start, 'seconds': time.time() - start, 'stop_reason': stopped or 'cli_exit',
             'model': 'gpt-6.1-terra', 'reasoning_effort': 'low', 'cpu_affinity': cpus}
    (directory / 'status.json').write_text(json.dumps(state, indent=2))
    print(json.dumps(state), flush=True)
    return state


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', required=True)
    parser.add_argument('--prompt', required=True)
    parser.add_argument('--image')
    parser.add_argument('--seconds', type=int, default=1500)
    parser.add_argument('--cpus', default='32,33,34,35,36,37,38,39')
    args = parser.parse_args()
    execute(Path(args.directory), Path(args.prompt).read_text(), args.image,
            args.seconds, [int(v) for v in args.cpus.split(',')])
