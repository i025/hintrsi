#!/usr/bin/env python3
"""Audit saved tool evidence without starting processes, tools, or models."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def main():
    suite = json.loads((OUT / 'stress_result.json').read_text())
    rows = []
    for summary in suite['cases']:
        case = summary['case']
        messages = json.loads((OUT / 'cases' / case['name'] / 'sdk_messages.json').read_text())
        checks = []
        for phase in ['initial', 'resume'] if case['resume'] else ['initial']:
            read_count = 20 if case['hook'] and phase == 'initial' else 1
            expected = {f'{phase}-read-{number}' for number in range(read_count)}
            expected.update({phase + '-edit', phase + '-test'})
            results = [block for item in messages if item['phase'] == phase
                       for block in item['message'].get('content', [])
                       if isinstance(block, dict) and block.get('tool_use_id')]
            identifiers = [block['tool_use_id'] for block in results]
            bash = [block for block in results if block['tool_use_id'] == phase + '-test']
            check = {'phase': phase, 'expected_tool_results': len(expected),
                     'observed_tool_results': len(results),
                     'exact_tool_result_ids': len(results) == len(expected) and set(identifiers) == expected,
                     'all_tools_succeeded': all(not block.get('is_error') for block in results),
                     'bash_test_marker_received': len(bash) == 1 and 'LOCAL_TEST_PASSED' in json.dumps(bash[0].get('content'))}
            checks.append(check)
        rows.append({'case': case, 'checks': checks, 'passed': summary['passed'] and
                     all(row['exact_tool_result_ids'] and row['all_tools_succeeded'] and
                         row['bash_test_marker_received'] for row in checks)})
    native = [row for row in rows if not row['case']['jit_off']]
    candidate = [row for row in rows if row['case']['jit_off']]
    result = {'kind': 'post_hoc_saved_evidence_audit', 'new_executions': 0, 'real_model_calls': 0,
              'suite_status': suite['status'], 'native_passed': sum(row['passed'] for row in native),
              'native_completed': len(native), 'candidate_passed': sum(row['passed'] for row in candidate),
              'candidate_completed': len(candidate), 'cases': rows}
    result['passed'] = (suite['status'] == 'candidate_passed_20_fresh_sessions'
                        and len(native) == 6 and len(candidate) == 20
                        and all(row['passed'] for row in rows))
    (OUT / 'tool_evidence_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ['passed', 'native_passed', 'native_completed',
                                                'candidate_passed', 'candidate_completed', 'new_executions']}))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
