"""Auxiliary RGB comparisons, with no claim to measure 3D reconstruction quality."""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / 'experiments/experiment_01_natural_trajectories'


def pixels(path, size=(640, 360)):
    return np.asarray(Image.open(path).convert('RGB').resize(size, Image.Resampling.LANCZOS), dtype=np.float64) / 255


def metrics(left, right):
    a, b = pixels(left), pixels(right)
    average_a = gaussian_filter(a, sigma=(1.5, 1.5, 0))
    average_b = gaussian_filter(b, sigma=(1.5, 1.5, 0))
    variance_a = gaussian_filter(a * a, sigma=(1.5, 1.5, 0)) - average_a ** 2
    variance_b = gaussian_filter(b * b, sigma=(1.5, 1.5, 0)) - average_b ** 2
    covariance = gaussian_filter(a * b, sigma=(1.5, 1.5, 0)) - average_a * average_b
    ssim = ((2 * average_a * average_b + .01 ** 2) * (2 * covariance + .03 ** 2) /
            ((average_a ** 2 + average_b ** 2 + .01 ** 2) * (variance_a + variance_b + .03 ** 2)))
    return {'mae_rgb': float(np.mean(np.abs(a - b))), 'ssim_rgb_gaussian_auxiliary': float(np.mean(ssim)),
            'pixel_identical': bool(np.array_equal(a, b))}


def main():
    scenes = {row['id']: row for row in json.loads((ROOT / 'configs/scenes.json').read_text())['scenes']}
    results = []
    revisions = []
    image_audit = []
    for scene, configuration in scenes.items():
        initial_files = []
        for repetition in range(1, 4):
            run = EXPERIMENT / 'runs' / (scene + '-R' + str(repetition))
            request = json.loads((run / 'bridge/model_requests.jsonl').read_text().splitlines()[0])
            images = json.loads((run / 'bridge' / request['request_id'] / 'image_attachments.json').read_text())
            initial_files.append(Path(images[0]['path']))
            row = {'run': run.name, 'reference_vs_final': metrics(configuration['reference'], run / 'workspace/final.png'),
                   'original_vs_regenerated': metrics(run / 'workspace/final.png', run / 'analysis/technical/replica/final.png')}
            results.append(row)
            renders = sorted((run / 'capture').glob('blender_*/artifacts/final.png'))
            if len(renders) > 1:
                revisions.append({'run':run.name, 'first_actual_render':str(renders[0].relative_to(ROOT)),
                                  'last_actual_render':str(renders[-1].relative_to(ROOT)),
                                  'reference_vs_first':metrics(configuration['reference'],renders[0]),
                                  'reference_vs_last':metrics(configuration['reference'],renders[-1])})
        image_audit.append({'scene': scene, 'media_type': 'image/jpeg',
                            'model_image_resolution': list(Image.open(initial_files[0]).size),
                            'original_resolution': list(Image.open(configuration['reference']).size),
                            'three_initial_image_contents_equal': all(path.read_bytes() == initial_files[0].read_bytes() for path in initial_files),
                            'original_vs_sdk_image': metrics(configuration['reference'], initial_files[0])})
    (EXPERIMENT / 'analysis/image_metrics.json').write_text(json.dumps({
        'scope': 'Auxiliary pixel appearance only; sensitive to viewpoint/background, not a comprehensive or 3D quality score.',
        'formula': 'RGB mean SSIM with Gaussian sigma1.5, C1=.01^2, C2=.03^2; images normalized 0..1 and resized to640x360.',
        'runs': results, 'revisions': revisions, 'sdk_image_preprocessing': image_audit}, indent=2))
    for row in results:
        print(row['run'], row['reference_vs_final'], 'repro', row['original_vs_regenerated'])


if __name__ == '__main__':
    main()
