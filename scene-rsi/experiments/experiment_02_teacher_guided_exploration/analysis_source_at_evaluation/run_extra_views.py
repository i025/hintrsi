"""Render additional evaluation views after all student sessions have ended."""
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/experiment_01_natural_trajectories'
assert (EXPERIMENT / 'batch_finished.json').exists()
for run in sorted((EXPERIMENT / 'runs').iterdir()):
    directory = run / 'analysis/technical'
    argv = json.loads((directory / 'regeneration_command.json').read_text())
    argv = argv[:argv.index('--')] + ['--', '/runtime/bin/blender', '--background',
                                     '/original/scene.blend', '--disable-autoexec',
                                     '--python', '/analysis/extra_views.py']
    (directory / 'extra_views_command.json').write_text(json.dumps(argv, indent=2))
    with (directory / 'extra_views.log').open('wb') as output:
        result = subprocess.run(['nice', '-n', '15', 'taskset', '-c', '48-55', *argv],
                                stdout=output, stderr=subprocess.STDOUT, timeout=180)
    print(run.name, 'extra views', result.returncode, flush=True)
