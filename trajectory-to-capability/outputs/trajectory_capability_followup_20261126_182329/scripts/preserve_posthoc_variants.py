"""Preserve both read-only audit responses after adding the public task description."""
import json
from pathlib import Path

OUT = Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
name = 'posthoc_development_aiomonitor-task-snapshots-diff_K2_v1'
session = 'capability-' + name
requests = {}
for line in (OUT / 'logs/bridge/model_requests.jsonl').open():
    row = json.loads(line)
    if row['session'] == session:
        requests[row['request_id']] = row
records = []
for line in (OUT / 'logs/bridge/model_responses.jsonl').open():
    row = json.loads(line)
    if row['session'] != session:
        continue
    request = requests[row['request_id']]
    described = 'original_public_task_description' in json.dumps(request['request'])
    suffix = 'with_public_description' if described else 'before_public_description'
    destination = OUT / 'audit' / (name + '_' + suffix + '.md')
    content = row['response']['choices'][0]['message']['content'] + '\n'
    if not destination.exists():
        destination.write_text(content)
    records.append({'request_id': row['request_id'], 'public_description_supplied': described,
        'request_timestamp': request['timestamp'], 'response_timestamp': row['timestamp'],
        'elapsed_seconds': row['elapsed_seconds'], 'preserved_report': str(destination)})
    if described:
        (OUT / 'audit' / (name + '.md')).write_text(content)
(OUT / 'audit/posthoc_description_correction.json').write_text(json.dumps({
    'records': records, 'pending_responses': sorted(set(requests)-{r['request_id'] for r in records}),
    'note': 'A second read-only analysis was launched before the first finished when adding the public task description. Both raw requests/responses are retained and reports exported separately. Canonical report uses the request with the description, independent of outcomes. One extra audit call is charged; no student, extraction candidate, test, patch or grade changes.'}, indent=2) + '\n')
print(json.dumps({'preserved_responses': len(records), 'requests': len(requests)}), flush=True)
