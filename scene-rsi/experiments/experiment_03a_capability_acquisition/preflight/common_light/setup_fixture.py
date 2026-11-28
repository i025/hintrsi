"""Artificial world/light changes test the common condition, without model calls."""
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[4]
BASE = Path(__file__).resolve().parent
SOURCE = BASE.parent / 'deterministic_evaluation/runs/A-T01-A0/workspace/build.py'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'analysis'))
from harness.isolation import command
from evaluate_capability_acquisition import environment, blender, invoke, write

(BASE / 'unused_model_socket').touch()
scenes = []
for index in (1, 2, 3):
    identity = 'A-T' + str(index).zfill(2)
    run = BASE / 'runs' / (identity + '-A0')
    for name in ('workspace', 'home', 'capture', 'tmp', 'inputs'):
        (run / name).mkdir(parents=True, exist_ok=True)
    (run / 'inputs/session.json').write_text('{}')
    write(run / 'status.json', {'status': 'completed', 'synthetic_fixture': True})
    write(run / 'sdk_command.json', command(run, BASE / 'unused_model_socket'))
    if index == 3:
        # A completed agent session can have no deliverable; do not manufacture one.
        continue
    source = SOURCE.read_text()
    emission = "m.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(.1,.2,.5,1)\nm.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.2\n"
    perturbation = ''
    if index == 2:
        perturbation = "s.world.use_nodes=True\ns.world.node_tree.nodes.get('Background').inputs['Color'].default_value=(.1,.3,.8,1)\ns.world.node_tree.nodes.get('Background').inputs['Strength'].default_value=3\ns.view_settings.exposure=1.25\nfor fixture_light in [o for o in bpy.data.objects if o.type=='LIGHT']:\n fixture_light.data.energy=3500;fixture_light.data.color=(.1,.8,.2)\n"
    source = source.replace("bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend')", emission + perturbation + "bpy.ops.wm.save_as_mainfile(filepath='/app/scene.blend')")
    (run / 'workspace/build.py').write_text(source)
    output = run / 'fixture_generation'
    argv = environment(run, output, run / 'workspace')
    result = invoke(blender(argv, '/app/build.py'), output, 'generate', '72-79', 120)
    assert result['exit_code'] == 0, result
    gt = BASE / 'private_fixture_gt' / identity
    gt.mkdir(parents=True, exist_ok=True)
    for name in ('scene.blend', 'final.png'):
        shutil.copy2(run / 'workspace' / name, gt / name)
    scenes.append({'id': identity, 'directory': str(gt), 'reference': str(gt / 'final.png')})
write(BASE / 'configs/data_split.json', {'test': scenes})
print('Two controlled scenes and one missing-deliverable fixture ready')
