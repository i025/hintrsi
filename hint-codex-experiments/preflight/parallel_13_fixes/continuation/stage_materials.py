"""Prepare original teacher prompts and the independent I fixture without model calls."""
import argparse
import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'source_parallel_13'
sys.path.insert(0, str(SOURCE))
sys.path.insert(0, str(SOURCE / 'benchmark/deepswe'))
from get_hint_by_task import HINT_AGENT_SYSTEM_PROMPT, HINT_AGENT_USER_PROMPT
from review_hint_traj import (REVIEW_SYSTEM_PROMPT, REVIEW_SYSTEM_PROMPT_SOLVED,
                              build_user_prompt, compress_trajectory)


def write(path, text):
    path.write_text(text, encoding='utf-8')
    return str(path)


def initial(issue, fixture, output):
    output.mkdir(parents=True, exist_ok=True)
    source = (fixture / 'window_report.py').read_text()
    repaired = source.replace("record['time'] < end", "record['time'] <= end")
    assert repaired != source
    golden = ''.join(difflib.unified_diff(source.splitlines(keepends=True),
                                         repaired.splitlines(keepends=True),
                                         fromfile='a/window_report.py', tofile='b/window_report.py'))
    files = {
        'system_prompt': write(output / 'teacher_system.md', HINT_AGENT_SYSTEM_PROMPT),
        'initial_prompt': write(output / 'teacher_initial.md', HINT_AGENT_USER_PROMPT.format(
            golden_diff_path='/tmp/golden_diff.diff', problem_statement=issue.read_text(),
            hint_output_path='/tmp/hint_output.md')),
        'golden_diff': write(output / 'golden_diff.diff', golden),
    }
    write(output / 'initial_manifest.json', json.dumps({
        'source': str(SOURCE), 'files': files, 'model_calls': 0,
        'golden_diff_container_path': '/tmp/golden_diff.diff',
        'golden_diff_student_visible': False,
        'scope': 'Original SDK and teacher prompts; synthetic fixture, not DeepSWE orchestration.',
    }, indent=2))
    return files


def review(trajs, hint, golden_diff, output, solved):
    output.mkdir(parents=True, exist_ok=True)
    compressed, stats = compress_trajectory(trajs)
    system = REVIEW_SYSTEM_PROMPT_SOLVED if solved else REVIEW_SYSTEM_PROMPT
    prompt = system + '\n\n' + build_user_prompt(compressed, hint.read_text(), golden_diff.read_text())
    prompt += '\n\nWrite your complete review to /tmp/review_output.md and include it in your final response.'
    write(output / 'teacher_review.md', prompt)
    write(output / 'compressed_traj.md', compressed)
    write(output / 'review_manifest.json', json.dumps({
        'source': str(SOURCE), 'trajs': str(trajs), 'hint': str(hint),
        'golden_diff': str(golden_diff), 'solved': solved, 'stats': stats,
        'model_calls': 0, 'stage_system_is_user_message': True,
        'teacher_system_remains_shared': True,
    }, indent=2))


def online(issue, fixture, hint, golden_diff, output, session, task, api_base):
    output.mkdir(parents=True, exist_ok=True)
    paths = ['/app/' + str(path.relative_to(fixture)) for path in sorted((fixture / 'data').glob('shard_*.json'))]
    assert len(paths) == 20, 'The independent fixture must have twenty data shards'
    requirement = ('\n\nPreexperiment data inspection requirement:\n'
                   'Before changing source files or running tests, inspect each data file listed below '
                   'using twenty separate Read tool calls. You may request these reads together. '
                   'Do not combine this inspection into a terminal command or delegate it. '
                   'After reading the data, continue solving and testing the original issue.\n\n')
    write(output / 'student_problem.txt', issue.read_text() + requirement + '\n'.join(paths) + '\n')
    registration = {'session': session, 'task': task, 'problem_statement': issue.read_text(),
                    'golden_diff': golden_diff.read_text(), 'current_hint': hint.read_text(),
                    'api_base': api_base, 'api_key': 'codex-local', 'model': 'gpt-6.1-terra'}
    write(output / 'registration.json', json.dumps(registration, indent=2))
    write(output / 'online_manifest.json', json.dumps({
        'source': str(SOURCE), 'student_problem': str(output / 'student_problem.txt'),
        'host_only_registration': str(output / 'registration.json'), 'data_paths': paths,
        'checkpoint_tools': 20, 'max_checks': 3, 'check_timeout_seconds': 600,
        'model_calls': 0, 'fixture_only_task_input_addition': requirement.strip(),
        'no_hint_is_valid': True, 'guidance_delivery_requires_separate_evidence': True,
    }, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='stage', required=True)
    first = commands.add_parser('initial')
    first.add_argument('--issue', type=Path, required=True)
    first.add_argument('--fixture', type=Path, required=True)
    later = commands.add_parser('review')
    for name in ('trajs', 'hint', 'golden-diff'):
        later.add_argument('--' + name, type=Path, required=True)
    later.add_argument('--solved', action='store_true')
    ongoing = commands.add_parser('online')
    for name in ('issue', 'fixture', 'hint', 'golden-diff'):
        ongoing.add_argument('--' + name, type=Path, required=True)
    ongoing.add_argument('--session', required=True)
    ongoing.add_argument('--task', default='window-report-inclusive-boundary')
    ongoing.add_argument('--api-base', default='http://127.0.0.1:8785/v1')
    for command in (first, later, ongoing):
        command.add_argument('--output', type=Path, required=True)
    args = vars(parser.parse_args())
    stage = args.pop('stage')
    globals()[stage](**args)


if __name__ == '__main__':
    main()
