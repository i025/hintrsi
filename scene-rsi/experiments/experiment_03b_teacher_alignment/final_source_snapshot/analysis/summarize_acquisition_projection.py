"""Pair measured 2D entities only when their exact GT instance sets agree."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03a_capability_acquisition'
CONTRASTS = [('A1', 'A0'), ('A3', 'A2'), ('A4', 'A1'), ('A5', 'A3'), ('A5', 'A4')]


def main():
    summary = json.loads((EXP / 'analysis/projection_summary.json').read_text())
    runs = {row['run_id']: row for row in summary['runs']}
    coverage = []
    for run, row in sorted(runs.items()):
        mappings = row['mappings']
        coverage.append({'run_id': run, 'proposals': len(mappings),
                         'status_counts': dict(Counter(item['status'] for item in mappings)),
                         'source_scene_exists': row.get('source_scene_exists'),
                         'measured_gt_instance_sets': [item['gt_instance_ids'] for item in mappings if item.get('metrics')],
                         'source': str(EXP / 'runs' / run / 'analysis/projection/result.json')})
    pairs = []
    scenes = json.loads((EXP / 'configs/data_split.json').read_text())['test']
    for scene in scenes:
        for first, second in CONTRASTS:
            identifiers = [scene['id'] + '-' + condition for condition in (first, second)]
            measured = [{tuple(sorted(item['gt_instance_ids'])): item for item in runs[identifier]['mappings']
                         if item.get('metrics')} for identifier in identifiers]
            shared = sorted(set(measured[0]) & set(measured[1]))
            entities = []
            for key in shared:
                left, right = measured[0][key], measured[1][key]
                a, b = left['metrics'], right['metrics']
                differences = {name: a[name] - b[name] if a[name] is not None and b[name] is not None else None
                               for name in ('iou', 'centroid_l2_normalized', 'bbox_iou', 'precision', 'recall')}
                entities.append({'gt_instance_ids': list(key),
                                 'first': {'label': left['gt_semantic_label'], 'metrics': a, 'evidence': left.get('evidence_directory')},
                                 'second': {'label': right['gt_semantic_label'], 'metrics': b, 'evidence': right.get('evidence_directory')},
                                 'first_minus_second': differences,
                                 'interpretation': 'Only this model-proposed, non-human-verified GT entity set is paired; labels, geometry and cameras may differ.'})
            pairs.append({'scene_id': scene['id'], 'conditions': [first, second], 'runs': identifiers,
                          'shared_measured_entities': entities,
                          'unpaired_instance_sets': [[list(key) for key in sorted(set(side) - set(shared))] for side in measured],
                          'status': 'measured_same_gt_entity_sets' if entities else 'unknown_no_shared_measured_entity_set'})
    result = {'coverage': coverage, 'paired_contrasts': pairs,
              'scope': 'Arithmetic on completed deterministic masks; no model calls, no semantic edits and no missing-value imputation.',
              'limits': ['Model-proposed correspondence is not human truth.',
                         'IoU increase and normalized centroid-distance decrease concern visible 2D agreement only.',
                         'No world position or 3D angle error is computed. Unknown and unmatched entities are not zero errors.',
                         'Per-run averages over different mapped object sets are not comparable group quality scores.',
                         'Visibility, opaque-proxy approximation, camera and geometry remain relevant.']}
    (EXP / 'analysis/paired_projection_differences.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print('Projection runs', len(runs), 'matched task contrasts', sum(bool(row['shared_measured_entities']) for row in pairs), '/', len(pairs))


if __name__ == '__main__':
    main()
