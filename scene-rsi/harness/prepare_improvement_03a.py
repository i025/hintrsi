"""Write external improvement input from Experiment03-A; this adapter grants no implicit evidence or GT."""
import argparse
import json
from pathlib import Path

from run_capability_acquisition import EXP, write


def configuration(condition, experiment=EXP, feedback=None, evidence=(), development_gt=(), history=(),
                  seconds=600, calls=24, cpus=None, port=19665):
    experiment = Path(experiment).resolve()
    frozen = json.loads((experiment / 'configs/frozen_libraries.json').read_text())
    source = next(row for row in frozen['libraries'] if row['condition'] == condition)
    split = json.loads((experiment / 'configs/data_split.json').read_text())
    return {
        'initial_library': str(experiment / 'libraries' / condition),
        'feedback': str(Path(feedback).resolve() if feedback else experiment / 'analysis/observed_results.json'),
        'evidence': [str(Path(path).resolve()) for path in evidence],
        'development_gt': [str(Path(path).resolve()) for path in development_gt],
        'history': [str(Path(path).resolve()) for path in history],
        'budget': {'seconds': seconds, 'calls': calls, 'cpus': cpus or list(range(32, 40)), 'port': port},
        'context': {'source_adapter': 'experiment03a', 'source_library_record': source,
                    'former_test_scene_ids': [scene['id'] for scene in split['test']],
                    'outcomes_used_for_improvement': 'historical_development_experience',
                    'generation_record': str(experiment / 'learning' / condition),
                    'validation_record': str(experiment / 'validation' / condition),
                    'note': 'Provenance paths grant no access. Select the actual generation, validation, trajectory, cost or GT files explicitly.'},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--condition', choices=['A1', 'A2', 'A3', 'A4', 'A5'], required=True)
    parser.add_argument('--experiment', type=Path, default=EXP)
    parser.add_argument('--feedback', type=Path)
    parser.add_argument('--evidence', type=Path, action='append', default=[])
    parser.add_argument('--gt', type=Path, action='append', default=[])
    parser.add_argument('--history', type=Path, action='append', default=[])
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--calls', type=int, default=24)
    parser.add_argument('--port', type=int, default=19665)
    parser.add_argument('--cpus', default='32,33,34,35,36,37,38,39')
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError('Choose a new input file; previous configurations are not overwritten.')
    write(args.output, configuration(args.condition, args.experiment, args.feedback, args.evidence,
          args.gt, args.history, args.seconds, args.calls, [int(cpu) for cpu in args.cpus.split(',')], args.port))


if __name__ == '__main__':
    main()
