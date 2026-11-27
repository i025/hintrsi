"""Account for reported CLI usage by real session, including superseded work."""
import csv
import json
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
usage=json.loads((OUT/'results/actual_usage_summary.json').read_text())
core={r['session'] for r in json.loads((OUT/'results/attempt_metrics.json').read_text())}
extra={r['run_name']+'-r1' for r in csv.DictReader((OUT/'extra_attempt_metrics.csv').open())}
missing=Counter(r['session'] for r in usage['usage_unreported_requests'])
def category(session):
    if session in core:return 'core_student'
    if session in extra:return 'superseded_student'
    if session.startswith('capability_hint_development_'):
        return 'optional_hint_teacher' if '_progress_' in session else 'optional_hint_student'
    if session.startswith(('capability-K0-','capability-K1-','capability-K2-')):
        group=session.split('-')[1]
        suffix='pre_metadatafix' if group in ['K1','K2'] and not session.endswith('-corrected') else 'final'
        return 'knowledge_'+group+'_'+suffix
    if 'preflight' in session or session=='capability-cli-probe':return 'engineering_preflight'
    if 'final-report' in session or 'summary-zh' in session:return 'report_presentation'
    if any(x in session for x in ['audit','posthoc','pooled','visual','scene-geometry','library-review']):return 'evidence_audit_and_review'
    return 'other_recorded_session'
rows=[];totals=defaultdict(lambda:defaultdict(int))
for session in sorted(set(usage['by_session'])|set(missing)):
    values=usage['by_session'].get(session,{})
    row={'category':category(session),'session':session,'model_calls_with_reported_usage':values.get('model_calls_with_usage',0),
        'usage_unreported_requests':missing[session]}
    for key in ['input_tokens','output_tokens','cached_input_tokens']:
        row['reported_'+key]=values.get(key,'')
    row['note']='Reported subset only; blank tokens are unknown, not zero. Cached input is a subset. Actual USD unknown.'
    rows.append(row)
    totals[row['category']]['model_calls_with_reported_usage']+=row['model_calls_with_reported_usage']
    totals[row['category']]['usage_unreported_requests']+=missing[session]
    for key in ['input_tokens','output_tokens','cached_input_tokens']:
        if key in values:totals[row['category']]['reported_'+key]+=values[key]
with (OUT/'results/cost_breakdown.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(OUT/'results/cost_breakdown_summary.json').write_text(json.dumps({'categories':dict(totals),
    'scope':'Only this experiment spawned CLI calls, including new audits of old evidence; historical original solver costs and this monitoring chat are excluded. SDK estimates are not added. Unknown usage is not assigned zero.'},indent=2)+'\n')
print(json.dumps({'sessions':len(rows),'categories':list(totals)}))
