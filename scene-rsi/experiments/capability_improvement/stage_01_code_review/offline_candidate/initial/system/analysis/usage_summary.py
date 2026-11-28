"""Report observed executor usage, preserving missing usage and failed attempts."""
from collections import Counter
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXP = ROOT / 'experiments/experiment_01_natural_trajectories'


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


def summarize(directory, scope, root=ROOT):
    requests = read_rows(directory / 'bridge/model_requests.jsonl')
    usage = read_rows(directory / 'bridge/token_usage.jsonl')
    totals = Counter()
    for item in usage:
        totals.update(item['usage'])
    reported = {row['request_id'] for row in usage}
    result = {'run': directory.name, 'scope': scope, 'directory': str(directory.relative_to(root)),
              'requests': len(requests), 'usage_records': len(usage), 'reported_tokens': dict(totals),
              'requests_without_usage': [row['request_id'] for row in requests if row['request_id'] not in reported],
              'actual_billing_usd': None}
    trajectory = directory / 'capture/trajs.json'
    status = directory / 'status.json'
    if trajectory.exists():
        result['sdk_wall_seconds'] = json.loads(trajectory.read_text())['metadata']['wall_seconds']
    if status.exists():
        state = json.loads(status.read_text())
        result['status'] = state['status']
        result['total_supervisor_seconds'] = state.get('total_seconds')
        result['sampled_peak_rss_sum_mib'] = state.get('peak_sampled_rss_sum_mib')
        result['reported_child_cpu_seconds'] = state.get('child_user_cpu_seconds', 0) + state.get('child_system_cpu_seconds', 0)
    return result


def main():
    records = [summarize(path, 'formal') for path in sorted((EXP / 'runs').iterdir())]
    records += [summarize(path, 'superseded_formal_start') for path in sorted((EXP / 'interrupted_memory_default/runs').iterdir())]
    for name in ['sdk_multimodal_01','sdk_multimodal_02','sdk_multimodal_03','parallel_lane_0','parallel_lane_1','memory_disabled','post_timeout_fix']:
        records.append(summarize(EXP / 'preflight' / name, 'engineering_preflight'))
    native = read_rows(EXP / 'preflight/native_cli/events.jsonl')
    native_usage = Counter()
    for event in native:
        if event['type'] == 'turn.completed':
            native_usage.update(event['usage'])
    grouped = {}
    for scope in ['formal','superseded_formal_start','engineering_preflight']:
        items = [row for row in records if row['scope'] == scope]
        tokens = Counter()
        for row in items:
            tokens.update(row['reported_tokens'])
        grouped[scope] = {'requests': sum(row['requests'] for row in items),
                          'usage_records': sum(row['usage_records'] for row in items),
                          'reported_tokens': dict(tokens),
                          'sdk_wall_seconds': sum(row.get('sdk_wall_seconds', 0) for row in items),
                          'missing_usage_requests': sum(len(row['requests_without_usage']) for row in items)}
    all_tokens = Counter(native_usage)
    for row in records:
        all_tokens.update(row['reported_tokens'])
    result = {'scopes': grouped, 'runs': records, 'superseded_native_diagnostic': {'turns': 1, 'usage': dict(native_usage)},
              'all_observed_executor_tokens': dict(all_tokens),
              'formal_batch': json.loads((EXP / 'batch_finished.json').read_text()),
              'actual_billing_usd': None, 'ofox_requests': 0,
              'limitations': ['Cancelled/terminated requests without returned usage are unknown; observed token totals are lower bounds.',
                              'Cached input and reasoning output are subsets, not extra tokens to add again.',
                              'SDK alias-based dollar estimates are not actual Codex subscription charges.',
                              'Controller chat tokens and provider-side GPU/CPU use are not observable through the executor.',
                              'RSS sums may count shared pages more than once; CPU counters are OS-reported children, not provider compute.']}
    (EXP / 'analysis/usage_summary.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(grouped, indent=2))
    print('all observed', dict(all_tokens))


if __name__ == '__main__':
    main()
