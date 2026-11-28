"""Independent reproduction, actual checkpoint states, and target diagnostics."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_02_teacher_guided_exploration'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def environment(run, output, replica):
    for name in ('capture', 'home', 'tmp', 'inputs'):
        (output / name).mkdir(parents=True, exist_ok=True)
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
            if target in mapped:argv[index + 1] = str(mapped[target])
            index += 3
        else:index += 1
    argv = argv[:argv.index('--')]
    scene = run.name[:3]
    return argv + ['--ro-bind', str(ROOT / 'analysis'), '/analysis',
                   '--ro-bind', str(run / 'workspace'), '/original',
                   '--ro-bind', str(run / 'capture'), '/checkpoints',
                   '--ro-bind', str(EXP / 'checkpoints' / scene), '/baseline']


def invoke(argv, output, name, cpus, timeout):
    command = ['nice', '-n', '15', 'taskset', '-c', cpus, *argv]
    write(output / (name + '_command.json'), command)
    started = time.time()
    with (output / (name + '.log')).open('wb') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            result = {'exit_code': code, 'seconds': time.time()-started, 'timeout': False}
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            result = {'exit_code': process.returncode, 'seconds': time.time()-started, 'timeout': True}
    write(output / (name + '_result.json'), result)
    return result


def evaluate(run, lane):
    started = time.time()
    cpus = '48-55' if lane == 0 else '56-63'
    output = run / 'analysis/technical'
    output.mkdir(parents=True)
    replica = output / 'replica'
    shutil.copytree(run / 'workspace', replica, ignore=shutil.ignore_patterns('.git'))
    for name in ('scene.blend','scene.blend1','scene.blend2','final.png'):
        (replica / name).unlink(missing_ok=True)
    argv = environment(run, output, replica)
    cases = {c['scene']:c for c in json.loads((EXP / 'configs/cases.json').read_text())}
    baseline_run = cases[run.name[:3]]['source_run']
    old_state = ROOT / 'experiments/experiment_01_natural_trajectories/runs' / baseline_run / 'analysis/technical/capture/final_state.json'
    shutil.copyfile(old_state, output / 'inputs/baseline_state.json')
    regeneration = invoke(argv + ['--', '/runtime/bin/blender', '--background', '--python', '/app/build.py'],
                          output, 'regeneration', cpus, 600)
    states = []
    if (run / 'workspace/scene.blend').exists():
        states.append({'input': '/original/scene.blend', 'output': '/capture/final_state.json'})
    if (replica / 'scene.blend').exists():
        states.append({'input': '/app/scene.blend', 'output': '/capture/regenerated_state.json'})
    for p in sorted((run / 'capture').glob('blender_*/artifacts/**/*.blend*')):
        relative = p.relative_to(run / 'capture')
        states.append({'input':'/checkpoints/'+str(relative), 'output':'/capture/states/'+str(relative)+'.json'})
    write(output / 'inputs/states.json', states)
    extraction = invoke(argv + ['--', '/runtime/bin/blender', '--background', '--disable-autoexec',
                                '--python', '/analysis/extract_checkpoints.py'],
                        output, 'state_extraction', cpus, 600)
    geometry = invoke(argv + ['--', '/runtime/bin/blender', '--background', '--disable-autoexec',
                             '--python', '/analysis/exploration_geometry.py', '--',
                             '--input', '/original/scene.blend', '--output', '/capture/target_geometry',
                             '--case', run.name[:3], '--baseline', '/baseline/scene.blend', '--mask'],
                      output, 'target_geometry', cpus, 600)
    extra = invoke(argv + ['--', '/runtime/bin/blender', '--background', '/original/scene.blend',
                          '--disable-autoexec', '--python', '/analysis/extra_views.py'],
                   output, 'extra_views', cpus, 600)
    result = {'run': run.name, 'regeneration': regeneration, 'state_extraction': extraction,
              'target_geometry': geometry, 'extra_views': extra,
              'source_entry_exists': (replica/'build.py').exists(),
              'regenerated_blend': (replica/'scene.blend').exists(), 'regenerated_render':(replica/'final.png').exists(),
              'original_blend_opened': (output/'capture/final_state.json').exists(),
              'seconds':time.time()-started,'cpu_set':cpus, 'evaluation_limit_seconds_per_stage':600,
              'scope':'Evaluation only after all student sessions end. No modeling repair or student feedback.'}
    write(output/'result.json',result)
    print(run.name, json.dumps(result),flush=True)
    return result


def baseline(scene):
    # Objective checks of the common input, performed only in the independent evaluation phase.
    run = next(p for p in sorted((EXP/'runs').iterdir()) if p.name.startswith(scene))
    output = EXP/'analysis/baselines'/scene
    replica = output/'replica'
    replica.mkdir(parents=True)
    argv = environment(run,output,replica)
    case = next(c for c in json.loads((EXP/'configs/cases.json').read_text()) if c['scene']==scene)
    state = ROOT/'experiments/experiment_01_natural_trajectories/runs'/case['source_run']/'analysis/technical/capture/final_state.json'
    shutil.copyfile(state,output/'inputs/baseline_state.json')
    return invoke(argv+['--','/runtime/bin/blender','--background','--disable-autoexec',
                         '--python','/analysis/exploration_geometry.py','--',
                         '--input','/baseline/scene.blend','--output','/capture/target_geometry',
                         '--case',scene,'--baseline','/baseline/scene.blend','--mask'],
                  output,'baseline_geometry','48-55',600)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run',action='append')
    parser.add_argument('--baselines',action='store_true')
    args=parser.parse_args()
    for run in (EXP/'runs').iterdir():
        state=json.loads((run/'status.json').read_text())
        if state['status'] in ('starting','running'):raise SystemExit('Students are still running')
    if args.baselines:
        for scene in ('S01','S02','S03'):print(scene,baseline(scene),flush=True)
    else:
        runs=[EXP/'runs'/name for name in args.run] if args.run else sorted((EXP/'runs').iterdir())
        def lane_work(lane):
            return [evaluate(run,lane) for run in runs[lane::2]]
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures=[executor.submit(lane_work,lane) for lane in range(2)]
            results=[future.result() for future in futures]
        write(EXP/'analysis/technical_summary.json',results)


if __name__=='__main__':main()
