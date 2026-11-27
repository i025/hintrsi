"""Add historical file links and recorded metadata; does not re-extract knowledge."""
import csv
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
SERVER=Path('/srv/lab-disks/disk2/users/xymo')
path=OUT/'trajectory_inventory.csv'
rows=list(csv.DictReader(path.open()))
fields=list(rows[0])
extra=['state_references','recorded_parent_status','recorded_terminal_reason','student_cli_session',
    'actual_model_calls_with_usage','actual_input_tokens','actual_output_tokens','actual_cached_input_tokens']
fields+=[k for k in extra if k not in fields]
states=defaultdict(list)
for p in (SERVER/'hint-codex-experiments/runs').rglob('experiment_state.json'):
    d=json.loads(p.read_text())
    for a in d.get('attempts',[]):
        if a.get('trajs_path'):states[a['trajs_path']].append((p,d,a))
usage=list(csv.DictReader((OUT/'audit/historical_cli_usage.csv').open()))
for row in rows:
    if row['project']!='hintrsi' or row['kind']!='student':continue
    p=Path(row['path']);links=json.loads(row['teacher_materials'] or '{}')
    refs=states.get(str(p),[])
    row['state_references']=json.dumps([str(x[0]) for x in refs])
    row['recorded_parent_status']=json.dumps(list(dict.fromkeys(x[1].get('status','') for x in refs)))
    if not row['group'] and '/hint-baseline-run/' in str(p):row['group']='B'
    if not row['round'] and 'infer_logs' in p.parts:row['round']='1'
    if refs:
        for state_path,d,a in refs:
            if not row['group']:row['group']=a.get('group','')
            if not row['round']:row['round']=a.get('round','')
            shared=d.get('shared',{}).get(row['task'],{})
            for key in ['full_hint','first_hint','teacher_state']:
                q=Path(shared.get(key,''))
                if q.is_file():links['available_shared_'+key]=str(q)
    if 'infer_logs' in p.parts:
        i=p.parts.index('infer_logs');run=Path(*p.parts[:i])
        loop=run.parent/re.sub(r'_r\d+$','',run.name)
        hint=loop/'hint_gen'/row['task']
        for name in ['hint_output.md',f"hint_compact_r{row['round']}.md"]:
            q=hint/name
            if q.is_file():links['available_'+name]=str(q)
        review=loop/'reviews'/row['task']/f"round_{row['round']}"
        if review.is_dir():links['available_review_after_round']=[str(q) for q in sorted(review.rglob('*')) if q.is_file() and q.name in ['review_hint_traj.md','review_hint_traj.json','review_output.md','trajs.json','trajs.json.gz']]
        prefix=re.sub(r'_[BHMI]_r\d+$','',run.name)
        session=f"{prefix}-{row['task']}-{row['group']}-r{row['round']}"
        matches=[u for u in usage if u['role']=='student' and u['session']==session]
        if '/parallel_13_fixes/real_sqlfmt/' in str(p):
            matches=[u for u in usage if u['role']=='student' and u['session']=='preflight13_sqlfmt-sqlfmt-create-table-ddl-formatting-B-r1']
        if len(matches)==1:
            u=matches[0];row['student_cli_session']=u['session']
            for src,dst in [('model_calls_with_usage','actual_model_calls_with_usage'),('input_tokens','actual_input_tokens'),('output_tokens','actual_output_tokens'),('cached_input_tokens','actual_cached_input_tokens')]:row[dst]=u[src]
            links['actual_model_request_ledger']=str(Path(u['ledger'])/'model_requests.jsonl')
            links['actual_model_response_ledger']=str(Path(u['ledger'])/'model_responses.jsonl')
            links['actual_token_usage_ledger']=str(Path(u['ledger'])/'token_usage.jsonl')
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:d=json.load(f)
    meta=d.get('metadata',{});result=meta.get('ResultMessage',{})
    row['recorded_terminal_reason']=meta.get('terminal_reason') or result.get('stop_reason') or meta.get('status','')
    links['scope_note']='Available archive links do not establish student receipt. Actual received text is evidenced only by captured system prompt or delivered online events. After-round review is not input to that round. Blank CLI usage means not linked/available, not zero.'
    row['teacher_materials']=json.dumps(links,ensure_ascii=False)
with path.open('w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
p=OUT/'audit/inventory_summary.json';summary=json.loads(p.read_text());summary.pop('deeply_audited',None)
summary['historical_student_rows_with_direct_cli_usage_link']=sum(bool(r.get('student_cli_session')) for r in rows)
summary['link_enrichment']='Added available full/compressed Hint, after-round review, state and CLI ledger references. No additional semantic deep audit or knowledge extraction.'
p.write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'student_rows':sum(r['project']=='hintrsi' and r['kind']=='student' for r in rows),'direct_cli_usage_links':summary['historical_student_rows_with_direct_cli_usage_link']}))
