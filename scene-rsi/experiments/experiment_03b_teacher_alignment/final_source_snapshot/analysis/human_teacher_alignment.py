"""Import genuine human exports and prepare development-only follow-up evidence."""
import argparse
import json
import math
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_03b_teacher_alignment'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def ranks(values):
    result = [0.0] * len(values)
    order = sorted(range(len(values)), key=lambda index: values[index])
    position = 0
    while position < len(order):
        end = position + 1
        while end < len(order) and values[order[end]] == values[order[position]]:
            end += 1
        rank = (position + end - 1) / 2 + 1
        for item in order[position:end]:
            result[item] = rank
        position = end
    return result


def spearman(first, second):
    if len(first) < 2:
        return None
    first, second = ranks(first), ranks(second)
    a, b = sum(first) / len(first), sum(second) / len(second)
    numerator = sum((x - a) * (y - b) for x, y in zip(first, second))
    denominator = math.sqrt(sum((x - a) ** 2 for x in first) * sum((y - b) ** 2 for y in second))
    return numerator / denominator if denominator else None


def kendall(first, second):
    concordant = discordant = first_ties = second_ties = 0
    for i in range(len(first)):
        for j in range(i + 1, len(first)):
            a, b = first[i] - first[j], second[i] - second[j]
            if a == b == 0:
                continue
            if a == 0: first_ties += 1
            elif b == 0: second_ties += 1
            elif a * b > 0: concordant += 1
            else: discordant += 1
    denominator = math.sqrt((concordant + discordant + first_ties) * (concordant + discordant + second_ties))
    return (concordant - discordant) / denominator if denominator else None


def import_annotations(source):
    source = Path(source)
    data = json.loads(source.read_text())
    if data.get('annotation_kind') != 'human':
        raise ValueError('Only a genuine human form export is accepted; blank templates are not annotations.')
    split = data['split']
    if split not in ('development', 'independent'):
        raise ValueError('The export must identify its actual split.')
    cases = json.loads((EXP / 'configs' / (split + '_cases.json')).read_text())
    identifiers = {case['anonymous_id'] for case in cases}
    if any(row['anonymous_id'] not in identifiers for row in data['ratings']):
        raise ValueError('Export case IDs do not belong to the declared split.')
    if not any(row.get('overall_fidelity') is not None or row.get('defects') for row in data['ratings']) and not any(row.get('preference') for row in data.get('preferences', [])):
        raise ValueError('An empty form is not genuine feedback.')
    target = EXP / 'human_annotations' / split / source.name
    if target.exists():
        raise ValueError('An import with this filename already exists; preserve prior annotations.')
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    compare(data, target.stem)
    print('Imported genuine', split, 'annotations:', target)


def compare(data, name):
    human = {row['anonymous_id']: row for row in data['ratings']}
    metrics = {}
    for condition in ('T0', 'T1'):
        predictions = {}
        for identifier in human:
            path = EXP / 'predictions' / (identifier + '-' + condition + '.json')
            if path.exists(): predictions[identifier] = json.loads(path.read_text())
        common = [identifier for identifier, row in human.items() if row.get('overall_fidelity') is not None and identifier in predictions]
        h = [human[identifier]['overall_fidelity'] for identifier in common]
        t = [predictions[identifier]['overall_fidelity_estimate'] for identifier in common]
        preference_results = []
        for row in data.get('preferences', []):
            if row.get('preference') in (None, 'uncertain') or row['first'] not in predictions or row['second'] not in predictions:
                continue
            difference = predictions[row['first']]['overall_fidelity_estimate'] - predictions[row['second']]['overall_fidelity_estimate']
            preference_results.append({'pair': row['id'], 'human': row['preference'], 'teacher_score_difference': difference,
                'teacher_preference_by_tie_tolerance': {str(tolerance): ('similar' if abs(difference) <= tolerance else ('A' if difference > 0 else 'B')) for tolerance in (0, 5, 10)}})
        defects = []
        for identifier in human:
            if identifier not in predictions:
                continue
            wanted = {item['category'] for item in human[identifier].get('defects', [])}
            model = sorted(predictions[identifier].get('main_defects', []), key=lambda item: item.get('priority', 99))
            defects.append({'anonymous_id': identifier, 'human_categories': sorted(wanted),
                           'teacher_top3_categories': [item['category'] for item in model[:3]],
                           'top3_category_coverage': len(wanted & {item['category'] for item in model[:3]}) / len(wanted) if wanted else None,
                           'category_matches': [{'category': item['category'], 'human_priority': item['priority'],
                               'human_severity': item.get('severity'), 'teacher_priority': other['priority'],
                               'teacher_severity': other.get('severity')} for item in human[identifier].get('defects', [])
                               for other in model if item['category'] == other['category']],
                           'scope': 'Exact category overlap only; not validated semantic defect matching.'})
        metrics[condition] = {'rated_cases': len(common), 'spearman': spearman(h, t), 'kendall_tau_b': kendall(h, t),
                              'preferences': preference_results,
                              'usable_preference_pairs': len(preference_results),
                              'preference_agreement_by_tie_tolerance': {
                                  str(tolerance): sum(row['teacher_preference_by_tie_tolerance'][str(tolerance)] == row['human'] for row in preference_results) / len(preference_results)
                                  if preference_results else None for tolerance in (0, 5, 10)},
                              'defect_category_overlap': defects,
                              'mean_top3_category_coverage': (sum(row['top3_category_coverage'] for row in defects if row['top3_category_coverage'] is not None)
                                  / sum(row['top3_category_coverage'] is not None for row in defects))
                                  if any(row['top3_category_coverage'] is not None for row in defects) else None}
    write(EXP / 'human_comparisons' / data['split'] / (name + '.json'),
          {'split': data['split'], 'reviewer': data.get('reviewer'), 'metrics': metrics,
           'human_page_open_seconds': data.get('seconds_since_page_open'),
           'human_timing_scope': data.get('timing_scope'),
           'limitations': 'One rater does not establish general human alignment. Scene versions are correlated. Severity/priority and semantic defect matching require actual manual review; exact category coverage is only an auxiliary measure.'})


def prepare_followup():
    sources = sorted((EXP / 'human_annotations/development').glob('*.json'))
    if not sources:
        raise ValueError('T2/T3 remain pending: genuine development human annotations have not been received.')
    target = EXP / 'alignment_inputs/development'
    target.mkdir(parents=True, exist_ok=True)
    for source in sources:
        shutil.copyfile(source, target / source.name)
    cases = json.loads((EXP / 'configs/development_cases.json').read_text())
    for case in cases:
        identifier = case['anonymous_id']
        dest = target / identifier
        dest.mkdir(exist_ok=True)
        for name in ('reference.png', 'final.png'):
            shutil.copyfile(Path(case['seed']) / name, dest / name)
        for condition in ('T0', 'T1'):
            shutil.copyfile(EXP / 'predictions' / (identifier + '-' + condition + '.json'), dest / (condition + '.json'))
    write(target / 'pending_plan.json', {'status': 'prepared_not_executed', 'sources': [str(path) for path in sources],
          'T2': 'Use genuine development cases to derive or retrieve rater-specific examples; keep model fixed.',
          'T3': 'Use actual development disagreements to propose critique-process changes; keep model fixed.',
          'next': 'Select a separate selection scene set, match budgets, validate candidates, freeze versions, then evaluate on held-out independent scenes and genuine independent human judgments.',
          'prohibited_input': 'Independent human annotations and independent-case teacher outputs must not be used for teacher adjustment.'})
    print('Prepared development-only evidence; no T2/T3 model has been run:', target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['import', 'prepare-followup'])
    parser.add_argument('--input')
    args = parser.parse_args()
    if args.stage == 'import': import_annotations(args.input)
    else: prepare_followup()
