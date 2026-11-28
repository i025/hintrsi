"""Measure 2D masks only for high-confidence, unambiguous SDK correspondences."""
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image

from evaluate_capability_acquisition import EXP, CPU_SETS, environment, blender, invoke, write


def mapping_filter(mappings, segmentation, correspondence_review=None):
    ids = set(int(item) for item in np.unique(segmentation)) - {0}
    gt_usage = Counter(item for row in mappings for item in row.get('gt_instance_ids', []))
    student_usage = Counter(item for row in mappings for item in row.get('student_object_names', []))
    review_by_index = {}
    for review in correspondence_review or []:
        index = review['mapping_index']
        review_by_index[index] = review if index not in review_by_index else None
    accepted, unknown = [], []
    for index, mapping in enumerate(mappings):
        review = review_by_index.get(index)
        row = {**mapping, 'mapping_index': index,
               'correspondence_source': 'SDK technical identity proposal plus planned SDK knowledge-comparison eligibility review; not human verified.',
               'projection_correspondence_review': review}
        reason = []
        gt_ids, names = row.get('gt_instance_ids', []), row.get('student_object_names', [])
        if row.get('confidence') != 'high':
            reason.append('Correspondence confidence is not high.')
        if not review or review.get('measurement_eligible') is not True:
            reason.append('No unique planned SDK comparison review explicitly marks this mapping eligible.')
        if not review or review.get('identity_ambiguity') != []:
            reason.append('Identity ambiguity is present or has not been explicitly cleared by the SDK comparison review.')
        if not gt_ids or any(item not in ids for item in gt_ids):
            reason.append('At least one GT instance ID has no visible pixels, or the ID list is empty.')
        if not names:
            reason.append('No student object name was mapped.')
        if any(gt_usage[item] > 1 for item in gt_ids) or any(student_usage[item] > 1 for item in names):
            reason.append('A GT ID or student name occurs in more than one mapping; instance assignment is unresolved.')
        if reason:
            unknown.append({**row, 'status': 'unknown', 'reasons': reason, 'metrics': None})
        else:
            accepted.append(row)
    return accepted, unknown


def bbox(mask):
    ys, xs = np.where(mask)
    return [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None


def mask_metrics(gt, student):
    height, width = gt.shape
    a, b = int(gt.sum()), int(student.sum())
    overlap = int(np.logical_and(gt, student).sum())
    union = int(np.logical_or(gt, student).sum())
    result = {'gt_visible_pixels': a, 'student_visible_pixels': b, 'intersection_pixels': overlap,
              'iou': overlap / union if union else None,
              'precision': overlap / b if b else None, 'recall': overlap / a if a else None,
              'student_gt_visible_area_ratio': b / a if a else None,
              'gt_bbox_xyxy': bbox(gt), 'student_bbox_xyxy': bbox(student)}
    centers = []
    for mask in (gt, student):
        ys, xs = np.where(mask)
        centers.append([float((xs.mean() + .5) / width), float((ys.mean() + .5) / height)] if len(xs) else None)
    result['gt_centroid_xy_normalized'], result['student_centroid_xy_normalized'] = centers
    result['centroid_delta_xy_normalized'] = [centers[1][i] - centers[0][i] for i in range(2)] if all(centers) else None
    result['centroid_l2_normalized'] = float(np.linalg.norm(result['centroid_delta_xy_normalized'])) if all(centers) else None
    left, right = result['gt_bbox_xyxy'], result['student_bbox_xyxy']
    if left and right:
        intersection = max(0, min(left[2], right[2]) - max(left[0], right[0])) * max(0, min(left[3], right[3]) - max(left[1], right[1]))
        area_a, area_b = (left[2] - left[0]) * (left[3] - left[1]), (right[2] - right[0]) * (right[3] - right[1])
        result['bbox_iou'] = intersection / (area_a + area_b - intersection)
    else:
        result['bbox_iou'] = None
    result['status'] = 'measured' if a and b else 'empty_visible_mask; center and undefined denominators remain unknown'
    return result


def evidence_images(output, index, gt, student, reference=None, reconstruction=None):
    folder = output / ('mapping_' + str(index).zfill(3))
    folder.mkdir(parents=True)
    Image.fromarray(gt.astype(np.uint8) * 255).save(folder / 'gt_mask.png')
    Image.fromarray(student.astype(np.uint8) * 255).save(folder / 'student_mask.png')
    overlay = np.zeros((*gt.shape, 3), dtype=np.uint8)
    overlay[gt] = (255, 70, 70)
    overlay[student] = (50, 130, 255)
    overlay[gt & student] = (255, 255, 255)
    image = Image.fromarray(overlay)
    image.save(folder / 'mask_overlay.png')
    bounds = bbox(gt | student)
    if bounds:
        crop = (max(0, bounds[0] - 12), max(0, bounds[1] - 12), min(640, bounds[2] + 12), min(360, bounds[3] + 12))
        image.crop(crop).save(folder / 'mask_overlay_crop.png')
        for label, path in (('reference', reference), ('reconstruction', reconstruction)):
            if path and Path(path).exists():
                rgb = Image.open(path).convert('RGB').resize((640, 360), Image.Resampling.LANCZOS)
                rgb.crop(crop).save(folder / (label + '_crop.png'))
    return str(folder)


def measure(run, scene, annotation_path, lane, args):
    output = run / 'analysis/projection'
    output.mkdir(parents=True)
    annotation = json.loads(annotation_path.read_text())
    segmentation_path = Path(scene['directory']) / 'instance_segmentation.png'
    original_segmentation = np.asarray(Image.open(segmentation_path))
    segmentation = np.asarray(Image.fromarray(original_segmentation).resize((640, 360), Image.Resampling.NEAREST))
    mappings = annotation.get('semantic_correspondence', [])
    review = args.projection_reviews.get(run.name, [])
    accepted, records = mapping_filter(mappings, original_segmentation, review)
    identity_matches = annotation.get('run_id') == run.name and annotation.get('scene_id') == scene['id']
    if not identity_matches:
        records = [{**mapping, 'mapping_index': index, 'status': 'unknown', 'metrics': None,
                    'reasons': ['The reviewer run or scene identity does not match this evaluation source.']}
                   for index, mapping in enumerate(mappings)]
        accepted = []
    workspace = output / 'workspace_copy'
    shutil.copytree(run / 'workspace', workspace, ignore=shutil.ignore_patterns('.git', '__pycache__', '*.pyc'))
    argv = environment(run, output, workspace)
    write(output / 'inputs/projection_mappings.json', accepted)
    rendering = None
    if accepted and (workspace / 'scene.blend').exists():
        rendering = invoke(blender(argv, '/analysis/acquisition_projection_masks.py',
                                   ['--input', '/app/scene.blend', '--mappings', '/inputs/projection_mappings.json',
                                    '--output', '/capture/projection_masks', '--samples', str(args.samples)]),
                           output, 'projection_render', CPU_SETS[lane], args.stage_seconds)
    rendered_path = output / 'capture/projection_masks/render_record.json'
    rendered = json.loads(rendered_path.read_text()) if rendered_path.exists() else {'mappings': []}
    actual = {row['mapping_index']: row for row in rendered['mappings']}
    for mapping in accepted:
        index = mapping['mapping_index']
        record = actual.get(index)
        if not record or record['status'] != 'rendered':
            records.append({**mapping, 'status': 'unknown', 'metrics': None,
                            'reasons': [record.get('reason') if record else 'No actual mask was rendered.'],
                            'render_record': record})
            continue
        gt = np.isin(segmentation, mapping['gt_instance_ids'])
        if not gt.any() or rendered.get('original_settings', {}).get('render_border'):
            records.append({**mapping, 'status': 'unknown', 'metrics': None,
                            'reasons': ['GT visible pixels vanished under nearest resizing, or the original used an unsupported render border.'],
                            'render_record': record})
            continue
        mask_path = output / 'capture/projection_masks' / Path(record['mask']).name
        student = np.asarray(Image.open(mask_path).convert('L')) >= 128
        measurements = mask_metrics(gt, student)
        folder = evidence_images(output, index, gt, student, scene['reference'], run / 'workspace/final.png')
        records.append({**mapping, 'status': measurements['status'], 'metrics': measurements,
                        'evidence_directory': folder, 'render_record': record})
    result = {'run_id': run.name, 'scene_id': scene['id'], 'annotation': str(annotation_path), 'completed': True,
              'source_scene_exists': (workspace / 'scene.blend').exists(),
              'protocol_version': 'v2_explicit_identity_eligibility_review',
              'correspondence_basis': 'Frozen original SDK technical proposals and planned knowledge-comparison eligibility judgments, not human verified.',
              'eligibility_review_source': str(args.comparison),
              'eligibility_review_source_available': args.comparison.exists(),
              'reviewer_identity_matches': identity_matches,
              'gt_mask_source': str(segmentation_path), 'gt_original_resolution': [original_segmentation.shape[1], original_segmentation.shape[0]],
              'gt_resize': 'Nearest-neighbor instance-ID map, 640x360; RGB is never used to infer GT masks.',
              'student_camera': 'Unchanged original active camera, evaluated opaque geometry proxies.',
              'rendering': rendering, 'render_approximation': rendered.get('approximation'),
              'original_settings': rendered.get('original_settings'),
              'mappings': sorted(records, key=lambda row: row['mapping_index']),
              'normalized_center_convention': 'Mean visible pixel centers ((x+0.5)/width, (y+0.5)/height), x rightward and y downward; L2 in these normalized coordinates.',
              'alignment': '2D original image frames only; no 3D coordinate, scale, position or angle alignment or error.',
              'unmatched_objects': 'Not imputed. Missing, ambiguous, low-confidence or duplicate mappings remain unknown.',
              'empty_mask': 'Visible IoU/recall can be zero, but absent center/precision remain undefined; no zero-error imputation.',
              'model_calls': 0, 'gt_mounted_in_mask_process': False, 'student_scene_modified': False}
    write(output / 'result.json', result)
    print(run.name, 'projection mappings', len(records), flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--experiment', type=Path, default=EXP)
    parser.add_argument('--run', action='append')
    parser.add_argument('--workers', type=int, default=4, choices=(1, 2, 3, 4))
    parser.add_argument('--samples', type=int, default=4)
    parser.add_argument('--stage-seconds', type=int, default=600)
    parser.add_argument('--comparison', type=Path)
    args = parser.parse_args()
    args.experiment = args.experiment.resolve()
    args.comparison = args.comparison or args.experiment / 'acquisition_reviews/knowledge-comparison/COMPARISON/workspace/knowledge_comparison.json'
    comparison = json.loads(args.comparison.read_text()) if args.comparison.exists() else {}
    args.projection_reviews = {row['run_id']: row['mappings']
                               for row in comparison.get('projection_correspondence_review', [])}
    all_runs = sorted((args.experiment / 'runs').iterdir())
    for run in all_runs:
        if (run / 'status.json').exists() and json.loads((run / 'status.json').read_text())['status'] in ('starting', 'running'):
            raise SystemExit('Student sessions are still active: ' + run.name)
    scenes = {row['id']: row for row in json.loads((args.experiment / 'configs/data_split.json').read_text())['test']}
    runs = [args.experiment / 'runs' / name for name in args.run] if args.run else all_runs
    def lane_work(lane):
        results = []
        for run in runs[lane::args.workers]:
            annotation = args.experiment / 'acquisition_reviews/technical' / run.name / 'workspace/technical_annotation.json'
            if annotation.exists():
                results.append(measure(run, scenes[run.name.rsplit('-', 1)[0]], annotation, lane, args))
            else:
                results.append({'run_id': run.name, 'status': 'unknown', 'completed': False,
                                'reason': 'No actual SDK technical semantic correspondence is available.', 'mappings': []})
        return results
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [executor.submit(lane_work, lane) for lane in range(args.workers)]
        results = [row for future in futures for row in future.result()]
    available = {run.name: json.loads((run / 'analysis/projection/result.json').read_text())
                 for run in all_runs if (run / 'analysis/projection/result.json').exists()}
    available.update({row['run_id']: row for row in results})
    write(args.experiment / 'analysis/projection_summary.json',
          {'completed_at_utc': datetime.now(timezone.utc).isoformat(), 'runs': list(available.values()),
           'complete': args.comparison.exists() and len(available) == len(all_runs) and all(row['completed'] for row in available.values()),
           'expected_run_count': len(all_runs), 'evaluated_now': len(results),
           'workers': args.workers, 'threads_each': 8, 'samples': args.samples,
           'protocol_version': 'v2_explicit_identity_eligibility_review',
           'eligibility_review_source': str(args.comparison),
           'eligibility_review_source_available': args.comparison.exists(),
           'model_calls': 0, 'human_verified_correspondence': False})


if __name__ == '__main__':
    main()
