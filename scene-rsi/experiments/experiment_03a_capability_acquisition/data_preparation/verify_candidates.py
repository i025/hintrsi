"""Open actual GT files, inspect Blender data, and compare low-cost validation renders."""
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import subprocess
import time

import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
BLENDER = '/srv/lab-disks/disk2/users/xymo/environments/image-to-3d-harness/opt/blender-5.2.2-linux-x64/blender'
DEVELOPMENT = [('S01', 'office/office_s1210607561'),
               ('S02', 'bedroom/bedroom_s1379154150'),
               ('S03', 'kitchen/kitchen_s1075679984')]


def limits():
    resource.setrlimit(resource.RLIMIT_AS, (32 * 1024 ** 3, 32 * 1024 ** 3))


def mask_statistics(folder, output):
    segmentation = np.asarray(Image.open(folder / 'instance_segmentation.png'))
    metadata = json.loads((folder / 'metadata.json').read_text())
    index_map = metadata.get('instance_map', {}).get('object_index_map', {})
    rows = []
    for key, name in index_map.items():
        ys, xs = np.where(segmentation == int(key))
        rows.append({'instance_id': int(key), 'dataset_instance_name': name,
                     'visible_pixels': len(xs),
                     'bbox_xyxy_pixels': [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None,
                     'centroid_xy_pixels': [float(xs.mean()), float(ys.mean())] if len(xs) else None,
                     'frame_fraction': float(len(xs) / segmentation.size)})
    result = {'resolution': [segmentation.shape[1], segmentation.shape[0]],
              'coordinate_convention': 'pixel x left-to-right, pixel y top-to-bottom',
              'instance_mapping_source': 'metadata.instance_map.object_index_map',
              'instances': rows,
              'limits': 'Visible masks are observed reference pixels. They do not establish hidden surfaces, pairwise depth order, or a semantic name match to Blender objects.'}
    (output / 'reference_instance_statistics.json').write_text(json.dumps(result, indent=2))


def inspect(identity, folder, development=False):
    output = OUT / ('development_gt' if development else 'new_scene_validation') / identity
    output.mkdir(parents=True, exist_ok=True)
    state = output / 'full_state.json'
    render = output / 'validation_render.png'
    command = ['nice', '-n', '15', 'taskset', '-c', '56-63', BLENDER,
               '--background', '--threads', '8', '--python-exit-code', '1',
               '--python', str(ROOT / 'analysis/inspect_gt_03.py'), '--',
               '--input', str(folder / 'scene.blend'), '--output', str(state)]
    if not development:
        command += ['--render', str(render), '--samples', '16']
    started = time.time()
    if not state.exists() or (not development and not render.exists()):
        with (output / 'inspection.log').open('w') as log:
            process = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                     timeout=600, preexec_fn=limits)
        returncode = process.returncode
    else:
        returncode = 0
    actual = json.loads(state.read_text()) if state.exists() else None
    result = {'id': identity, 'gt_directory': str(folder), 'command': command,
              'returncode': returncode, 'seconds': time.time() - started,
              'inspection_file': str(state), 'development': development,
              'missing_external_images': [item for item in actual['images'] if item['missing_external']] if actual else None,
              'objects': len(actual['objects']) if actual else None,
              'materials': len(actual['materials']) if actual else None,
              'node_groups': len(actual['node_groups']) if actual else None,
              'library_dependencies': actual['libraries'] if actual else None}
    if actual:
        result['material_node_types'] = sorted({node['type'] for material in actual['materials']
                                                for node in (material['tree'] or {}).get('nodes', [])})
        mask_statistics(folder, output)
    if render.exists():
        image = Image.open(folder / 'color.png').convert('RGB').resize((640, 360), Image.Resampling.LANCZOS)
        reference = np.asarray(image).astype(np.float32) / 255
        rendered = np.asarray(Image.open(render).convert('RGB')).astype(np.float32) / 255
        result['validation_render'] = {'path': str(render), 'reference_resolution': list(Image.open(folder / 'color.png').size),
                                        'resolution': [640, 360], 'samples': 16, 'device': 'CPU',
                                        'mae_rgb': float(np.abs(reference - rendered).mean()),
                                        'ssim_rgb_gaussian_auxiliary': float(structural_similarity(reference, rendered,
                                                                                                 data_range=1, channel_axis=2,
                                                                                                 gaussian_weights=True)),
                                        'limits': 'Low-cost rerender differs in resolution and samples from dataset RGB; metrics check gross agreement, not pixel-identical reproduction.'}
    (output / 'validation.json').write_text(json.dumps(result, indent=2))
    print(identity, 'done', result['seconds'], 'seconds', flush=True)
    return result


if __name__ == '__main__':
    development = []
    for identity, relative in DEVELOPMENT:
        development.append(inspect(identity, ROOT / 'data/evaluation_gt' / relative, True))
    (OUT / 'development_gt_manifest.json').write_text(json.dumps({'scenes': development}, indent=2))
    print('Development GT package ready', flush=True)
    candidates = json.loads((OUT / 'new_scene_candidates.json').read_text())
    rows = [inspect(item['id'], Path(item['directory'])) for item in candidates['scenes']]
    (OUT / 'new_scene_validation.json').write_text(json.dumps({'completed_at_utc': datetime.now(timezone.utc).isoformat(),
                                                             'scenes': rows}, indent=2))
