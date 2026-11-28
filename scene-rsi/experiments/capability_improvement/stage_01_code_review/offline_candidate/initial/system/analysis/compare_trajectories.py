"""Compare evidence-grounded semantic annotations, not source text."""
from collections import Counter
from itertools import combinations
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'experiments/experiment_01_natural_trajectories/analysis'


def jaccard(left, right):
    return len(left & right) / len(left | right) if left | right else None


def sequence_similarity(left, right):
    previous = list(range(len(right) + 1))
    for index, item in enumerate(left, 1):
        current = [index]
        for other_index, other in enumerate(right, 1):
            current.append(min(current[-1] + 1, previous[other_index] + 1,
                               previous[other_index - 1] + (item != other)))
        previous = current
    length = max(len(left), len(right))
    return 1 - previous[-1] / length if length else None


def main():
    annotations = json.loads((OUTPUT / 'annotations.json').read_text())
    pairs = []
    recurrence = {}
    for scene in ('S01', 'S02', 'S03'):
        runs = [(scene + '-R' + str(rep), annotations['runs'][scene + '-R' + str(rep)]) for rep in range(1, 4)]
        frequencies = Counter(defect['id'] for _, run in runs for defect in run['defects'])
        recurrence[scene] = dict(frequencies)
        for (left_name, left), (right_name, right) in combinations(runs, 2):
            left_strategies = {label for label, evidence in left['strategies'].items() if evidence['status'] in ('executed', 'retained')}
            right_strategies = {label for label, evidence in right['strategies'].items() if evidence['status'] in ('executed', 'retained')}
            left_state = set(left['state_components'])
            right_state = set(right['state_components'])
            left_defects = {item['id'] for item in left['defects']}
            right_defects = {item['id'] for item in right['defects']}
            pairs.append({'scene': scene, 'left': left_name, 'right': right_name,
                          'strategy_jaccard': jaccard(left_strategies, right_strategies),
                          'shared_strategies': sorted(left_strategies & right_strategies),
                          'left_only_strategies': sorted(left_strategies - right_strategies),
                          'right_only_strategies': sorted(right_strategies - left_strategies),
                          'construction_sequence_similarity': sequence_similarity(left['construction_sequence'], right['construction_sequence']),
                          'tool_cycle_sequence_similarity': sequence_similarity(left['tool_sequence'], right['tool_sequence']),
                          'semantic_component_state_jaccard': jaccard(left_state, right_state),
                          'state_metric_scope': 'Observed semantic component presence in final 3D states; not coordinate error or intermediate state-trajectory alignment.',
                          'state_trajectory_similarity': None,
                          'state_trajectory_reason': 'Uneven sparse saved checkpoints and no reliable semantic state alignment; not imputed.',
                          'shared_defects': sorted(left_defects & right_defects),
                          'defect_jaccard': jaccard(left_defects, right_defects)})
    result = {'pairs': pairs, 'defect_recurrence_by_scene': recurrence,
              'independent_tasks': 3, 'same_task_pairs': 9,
              'statistical_significance_claim': False,
              'annotation_kind': 'Automated experiment-assistant posthoc observations with file/event/image evidence; no human labels.'}
    (OUTPUT / 'pairwise_metrics.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    columns = ['scene', 'left', 'right', 'strategy_jaccard', 'construction_sequence_similarity',
               'tool_cycle_sequence_similarity', 'semantic_component_state_jaccard', 'defect_jaccard']
    with (OUTPUT / 'pairwise_metrics.csv').open('w') as output:
        writer = csv.DictWriter(output, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(pairs)
    for pair in pairs:
        print(pair['left'], pair['right'], pair['strategy_jaccard'], pair['construction_sequence_similarity'])


if __name__ == '__main__':
    main()
