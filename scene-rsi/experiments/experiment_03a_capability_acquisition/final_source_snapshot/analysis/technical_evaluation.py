"""Re-execute delivered source in isolation, only after all student runs end."""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/experiment_01_natural_trajectories'


def evaluate(run):
    started = time.time()
    output = run / 'analysis/technical'
    output.mkdir(parents=True, exist_ok=True)
    replica = output / 'replica'
    shutil.copytree(run / 'workspace', replica, ignore=shutil.ignore_patterns('.git'))
    for name in ('scene.blend', 'scene.blend1', 'scene.blend2', 'final.png'):
        (replica / name).unlink(missing_ok=True)
    for name in ('capture', 'home', 'tmp', 'inputs'):
        (output / name).mkdir()
    argv = json.loads((run / 'sdk_command.json').read_text())
    mapped = {'/app': replica, '/capture': output / 'capture', '/home/student': output / 'home',
              '/tmp': output / 'tmp', '/inputs': output / 'inputs'}
    index = 0
    while index < len(argv):
        if argv[index] in ('--bind', '--ro-bind'):
            target = argv[index + 2]
            if target == '/model/proxy.sock':
                del argv[index:index + 3]
                continue
            if target in mapped:
                argv[index + 1] = str(mapped[target])
            index += 3
        else:
            index += 1
    separator = argv.index('--')
    argv = argv[:separator] + ['--ro-bind', str(ROOT / 'analysis'), '/analysis',
                              '--ro-bind', str(run / 'workspace'), '/original',
                              '--ro-bind', str(run / 'capture'), '/checkpoints',
                              '--', '/runtime/bin/blender', '--background', '--python', '/app/build.py']
    (output / 'regeneration_command.json').write_text(json.dumps(argv, indent=2))
    result = {'source_entry_exists': (replica / 'build.py').exists(), 'regeneration_exit_code': None}
    # Resource limits are applied by taskset/nice without thread-sensitive preexec hooks.
    command = ['nice', '-n', '15', 'taskset', '-c', '48-55', *argv]
    with (output / 'regeneration.log').open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            result['regeneration_exit_code'] = process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            result['regeneration_stop_reason'] = '180_second_evaluation_limit'
    result.update(regenerated_blend=(replica / 'scene.blend').exists(),
                  regenerated_render=(replica / 'final.png').exists())
    # Inspect original deliverables and every real saved scene checkpoint. No synthetic states.
    states = []
    if (run / 'workspace/scene.blend').exists():
        states.append({'input': '/original/scene.blend', 'output': '/capture/final_state.json'})
    if (replica / 'scene.blend').exists():
        states.append({'input': '/app/scene.blend', 'output': '/capture/regenerated_state.json'})
    for path in sorted((run / 'capture').glob('blender_*/artifacts/**/*.blend*')):
        relative = path.relative_to(run / 'capture')
        states.append({'input': '/checkpoints/' + str(relative),
                       'output': '/capture/states/' + str(relative) + '.json'})
    (output / 'inputs/states.json').write_text(json.dumps(states, indent=2))
    extract = argv[:argv.index('--')] + ['--', '/runtime/bin/blender', '--background', '--disable-autoexec',
                                       '--python', '/analysis/extract_checkpoints.py']
    with (output / 'state_extraction.log').open('wb') as log:
        completed = subprocess.run(['nice', '-n', '15', 'taskset', '-c', '48-55', *extract],
                                   stdout=log, stderr=subprocess.STDOUT, timeout=180)
    result.update(state_extraction_exit_code=completed.returncode,
                  original_blend_opened=(output / 'capture/final_state.json').exists(),
                  requested_saved_states=len(states),
                  extracted_saved_states=sum(row['opened'] for row in json.loads((output / 'capture/state_open_results.json').read_text())),
                  seconds=time.time() - started)
    (output / 'result.json').write_text(json.dumps(result, indent=2))
    print(run.name, json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    finished = json.loads((EXPERIMENT / 'batch_finished.json').read_text())
    assert not finished['interrupted'] and finished['unstarted'] == 0
    runs = sorted((EXPERIMENT / 'runs').iterdir())
    assert len(runs) == 9 and all(json.loads((run / 'status.json').read_text())['status'] != 'running' for run in runs)
    # Eight CPU cores total; evaluation remains separate from student execution.
    for run in runs:
        evaluate(run)
