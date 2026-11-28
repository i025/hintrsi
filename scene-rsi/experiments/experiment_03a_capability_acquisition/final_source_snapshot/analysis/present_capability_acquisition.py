"""Present observed artifacts and arithmetic contrasts without new model judgments."""
import csv
import html
import json
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03a_capability_acquisition'
OUT = EXP / 'analysis'
CONTRASTS = [('A1', 'A0'), ('A3', 'A2'), ('A4', 'A1'), ('A5', 'A3'), ('A5', 'A4')]


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def make_comparison(scenes, common_light=False):
    width, height, label = 420, 236, 30
    sheet = Image.new('RGB', (width * 7, (height + label) * len(scenes)), 'white')
    draw = ImageDraw.Draw(sheet)
    sections = []
    for y, scene in enumerate(scenes):
        if common_light:
            cells = [('GT common light', EXP / 'data_preparation/new_scene_validation' / scene['id'] / 'common_light/capture/common_light.png')]
            cells += [('A' + str(i), EXP / 'runs' / (scene['id'] + '-A' + str(i)) / 'analysis/technical/common_light/capture/common_light.png') for i in range(6)]
        else:
            cells = [('Reference', Path(scene['reference']))]
            cells += [('A' + str(i), EXP / 'runs' / (scene['id'] + '-A' + str(i)) / 'workspace/final.png') for i in range(6)]
        items = []
        for x, (title, path) in enumerate(cells):
            origin = (x * width, y * (height + label))
            draw.text((origin[0] + 8, origin[1] + 7), scene['id'] + ' | ' + title, fill='black')
            if path.exists():
                image = ImageOps.contain(Image.open(path).convert('RGB'), (width, height))
                sheet.paste(image, (origin[0] + (width - image.width) // 2, origin[1] + label + (height - image.height) // 2))
                source = html.escape(os.path.relpath(path, OUT))
                items.append('<figure><figcaption>' + title + '</figcaption><a href="' + source + '"><img src="' + source + '"></a></figure>')
            else:
                draw.text((origin[0] + 12, origin[1] + label + 80), 'No delivered image', fill='black')
                items.append('<figure><figcaption>' + title + '</figcaption><p>无交付图像</p></figure>')
        sections.append('<section><h2>' + scene['id'] + '</h2><div class="row">' + ''.join(items) + '</div></section>')
    sheet.save(OUT / ('comparison_common_light.png' if common_light else 'comparison_all_conditions.png'))
    return ''.join(sections)


def main():
    scenes = read(EXP / 'configs/data_split.json')['test']
    order = read(EXP / 'configs/acquisition_review_blind_order.json')
    anonymous = {row['run']: row['anonymous_id'] for row in order}
    rows = []
    for scene in scenes:
        for condition in range(6):
            name = scene['id'] + '-A' + str(condition)
            run = EXP / 'runs' / name
            status = read(run / 'status.json', {})
            result = read(run / 'analysis/technical/result.json', {})
            visual = read(EXP / 'acquisition_reviews/visual' / anonymous[name] / 'workspace/visual_evaluation.json', {})
            primary = result.get('source_only_reproduction', {})
            images = result.get('image_comparison', {})
            reference = images.get('reference_comparison') or {}
            rows.append({'run': name, 'scene': scene['id'], 'condition': 'A' + str(condition),
                         'status': status.get('status'), 'stop_reason': status.get('stop_reason'),
                         'seconds': status.get('total_seconds'), 'blender_executions': status.get('blender_executions'),
                         'complete_delivery': all((run / 'workspace' / name).exists() for name in ('build.py', 'scene.blend', 'final.png')),
                         'source_exists': (run / 'workspace/build.py').exists(),
                         'blend_exists': (run / 'workspace/scene.blend').exists(),
                         'render_exists': (run / 'workspace/final.png').exists(),
                         'source_only_portable': primary.get('source_portable_deliverables'),
                         'source_only_exit_code': primary.get('exit_code'),
                         'rgba_pixel_identical_after_regeneration': images.get('rgba_pixel_identical'),
                         'auxiliary_ssim': reference.get('ssim_rgb_gaussian_auxiliary'),
                         'model_visual_estimate_0_100': visual.get('overall_fidelity_estimate_0_100'),
                         'human_rating': None,
                         'technical_record': str(run / 'analysis/technical/result.json'),
                         'visual_record': str(EXP / 'acquisition_reviews/visual' / anonymous[name] / 'workspace/visual_evaluation.json')})
    write(OUT / 'observed_results.json', {'runs': rows, 'scope': 'Mechanical observations and copied automatic estimates, not human labels or a comprehensive quality score.'})
    with (OUT / 'observed_results.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    contrasts = []
    for scene in scenes:
        values = {row['condition']: row for row in rows if row['scene'] == scene['id']}
        for left, right in CONTRASTS:
            differences = {}
            for metric in ('auxiliary_ssim', 'model_visual_estimate_0_100'):
                a, b = values[left][metric], values[right][metric]
                differences[metric] = a - b if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
            contrasts.append({'scene': scene['id'], 'contrast': left + '-' + right, 'arithmetic_difference': differences})
    write(OUT / 'paired_observed_differences.json', {'pairs': contrasts, 'scope': 'Prespecified within-scene arithmetic differences only. Four scene pairs are not repeated library samples; no significance or causal tool-versus-text claim.'})
    original = make_comparison(scenes)
    common = make_comparison(scenes, common_light=True)
    (OUT / 'comparison.html').write_text('<!doctype html><meta charset="utf-8"><title>03-A 实际结果</title><style>body{font-family:sans-serif;margin:20px}.row{display:grid;grid-template-columns:repeat(7,minmax(180px,1fr));overflow:auto}figure{margin:4px}img{width:100%;min-width:180px}figcaption{font-weight:bold}</style><h1>03-A 参考图与实际交付</h1><p>显示真实图像；组名用于结果查阅。自动评价与人工评价分开，当前没有人工评分。</p>' + original + '<h1>统一白色世界光辅助对照</h1><p>保留各自的几何、材质、相机和材质发光；仍存在混杂，不能单独解释为材质质量。</p>' + common)
    print('Saved 24 observed rows, 20 paired arithmetic contrasts and actual-image comparison materials.')


if __name__ == '__main__':
    main()
