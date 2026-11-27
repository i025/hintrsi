"""Join original attempt tables to reported CLI deltas; never infer missing fees."""
import csv
import gzip
import json
import subprocess
import re
from collections import Counter,defaultdict
from pathlib import Path

OUT=Path(Path(__file__).with_name('ROOT.txt').read_text().strip())
SOURCE=Path('/srv/lab-disks/disk2/users/xymo/hint-codex-experiments')
files=[Path(p) for p in subprocess.check_output(['rg','--files',str(SOURCE)],text=True).splitlines()]
links=defaultdict(list)
def logical(path):return str(path).removesuffix('.gz')
for p in files:
    if p.name!='attempt_metrics.csv':continue
    metadata=p.with_name('metrics.json')
    data=json.loads(metadata.read_text()) if metadata.exists() else {}
    for row in csv.DictReader(p.open()):
        if row.get('trajs_path') and row.get('session'):
            links[logical(row['trajs_path'])].append({'metrics_file':str(p),'bridge':data.get('bridge_source'),**row})
usage={};requests={};turns={};all_role_usage=defaultdict(list)
for p in files:
    if p.name not in ('token_usage.jsonl','model_requests.jsonl','exec_turns.jsonl'):continue
    target={'token_usage.jsonl':usage,'model_requests.jsonl':requests,'exec_turns.jsonl':turns}[p.name]
    sessions=defaultdict(list)
    for line in p.open():
        try:d=json.loads(line)
        except ValueError:continue
        if p.name=='token_usage.jsonl':all_role_usage[(str(p),d.get('session'),d.get('role'),d.get('phase'))].append(d)
        if d.get('role')=='student' and d.get('phase')=='solve':sessions[d.get('session')].append(d)
    target[str(p.parent)]=sessions
inventory=list(csv.DictReader((OUT/'trajectory_inventory.csv').open()))
rows=[]
ledger_rows=[]
for (ledger,session,role,phase),values in sorted(all_role_usage.items(),key=lambda pair:str(pair[0])):
    item={'ledger':ledger,'session':session,'role':role,'phase':phase,'usage_records':len(values),
        'reported_calls_with_usage':len({x['request_id'] for x in values}) if all(x.get('request_id') for x in values) else '',
        'reported_cli_turns_with_usage':len({x['turn_id'] for x in values}) if all(x.get('turn_id') for x in values) else '',
        'input_tokens':'','output_tokens':'','cached_input_tokens':'',
        'scope':'Per original ledger. Copies/snapshots may overlap; do not sum all rows as independent billed calls.'}
    for target,field in [('input_tokens','inputTokens'),('output_tokens','outputTokens'),('cached_input_tokens','cachedInputTokens')]:
        if all(isinstance(x.get('delta',{}).get(field),(int,float)) for x in values):item[target]=sum(x['delta'][field] for x in values)
    ledger_rows.append(item)
with (OUT/'audit/historical_cli_usage_by_session.csv').open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(ledger_rows[0]));writer.writeheader();writer.writerows(ledger_rows)
for source in inventory:
    if source['project']!='hintrsi' or source['kind']!='student':continue
    path=Path(source['path']);data=json.loads(gzip.open(path,'rt').read() if path.suffix=='.gz' else path.read_text());meta=data.get('metadata',{});result=meta.get('ResultMessage',{})
    candidates=links.get(logical(path),[]);sessions={x['session'] for x in candidates}
    evidence=sorted({x['metrics_file'] for x in candidates})
    proxy=path.parent/'proxy.log'
    if not sessions and proxy.exists():
        sessions=set(re.findall(r'/sessions/([^/\s\x22]+)/student/solve/',proxy.read_text(errors='replace')))
        if sessions:evidence.append(str(proxy))
    row={'trajectory_path':str(path),'task':source['task'],'group':source['group'],'round':source['round'],
        'source_attempt_tables':json.dumps(sorted({x['metrics_file'] for x in candidates})),
        'session_link_evidence':json.dumps(evidence),
        'cli_session':next(iter(sessions)) if len(sessions)==1 else '',
        'cli_usage_ledger':'','equivalent_ledger_copies':'','cli_calls_with_usage':'','cli_turns_with_usage':'','cli_usage_events':'','cli_recorded_requests':'','cli_usage_missing_requests':'',
        'cli_input_tokens':'','cli_output_tokens':'','cli_cached_input_tokens':'','cli_turn_seconds':'',
        'sdk_reported_input_tokens':result.get('usage',{}).get('input_tokens',''),
        'sdk_reported_output_tokens':result.get('usage',{}).get('output_tokens',''),
        'sdk_reported_cached_input_tokens':result.get('usage',{}).get('cache_read_input_tokens',''),
        'student_wall_seconds':meta.get('wall_seconds',''),'student_sdk_seconds':result['duration_ms']/1000 if isinstance(result.get('duration_ms'),(int,float)) else '',
        'teacher_wait_seconds':meta.get('teacher_wait_seconds',''),'reported_attempt_wall_seconds':'',
        'coverage':'no_unambiguous_original_session_link','settled_dollar_cost':'','notes':'SDK dollar/token estimates are excluded. Missing CLI data remain blank.'}
    for x in candidates:
        if x.get('attempt_wall_seconds'):
            row['reported_attempt_wall_seconds']=x['attempt_wall_seconds'];break
    if row['cli_session']:
        session=row['cli_session']
        preferred={str(Path(x['bridge'])) for x in candidates if isinstance(x.get('bridge'),str)}
        found=[key for key in preferred if usage.get(key,{}).get(session)]
        if not found:found=[key for key,values in usage.items() if values.get(session)]
        if len(found)>1 and all(usage[key][session]==usage[found[0]][session] for key in found[1:]):
            row['equivalent_ledger_copies']=json.dumps(found)
            found=[min(found,key=len)]
            row['notes']+=' Original and archived ledger copies contain identical selected records; counted once by direct decoded-record comparison.'
        if len(found)==1:
            key=found[0];records=usage[key][session];row['cli_usage_ledger']=str(Path(key)/'token_usage.jsonl')
            row['cli_usage_events']=len(records)
            if all(x.get('request_id') for x in records):row['cli_calls_with_usage']=len({x['request_id'] for x in records})
            if all(x.get('turn_id') for x in records):row['cli_turns_with_usage']=len({x['turn_id'] for x in records})
            deltas=[x.get('delta',{}) for x in records]
            for target,field in [('cli_input_tokens','inputTokens'),('cli_output_tokens','outputTokens'),('cli_cached_input_tokens','cachedInputTokens')]:
                if all(isinstance(x.get(field),(int,float)) for x in deltas):row[target]=sum(x[field] for x in deltas)
            turn_records=turns.get(key,{}).get(session,[])
            if turn_records and all(isinstance(x.get('elapsed_seconds'),(int,float)) for x in turn_records):row['cli_turn_seconds']=sum(x['elapsed_seconds'] for x in turn_records)
            req=requests.get(key,{}).get(session,[])
            if req:
                ids={x.get('request_id') for x in records};row['cli_recorded_requests']=len(req)
                if all(x.get('request_id') for x in records+req):row['cli_usage_missing_requests']=sum(x['request_id'] not in ids for x in req)
            row['coverage']='reported_CLI_deltas_joined_by_original_attempt_session'
        elif len(found)>1:
            row['coverage']='ambiguous_multiple_original_ledgers';row['notes']+=' Candidate ledgers: '+json.dumps(found)
    rows.append(row)
output=OUT/'audit/historical_attempt_costs.csv'
with output.open('w',newline='') as stream:
    writer=csv.DictWriter(stream,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
summary={'student_files':len(rows),'coverage':dict(Counter(r['coverage'] for r in rows)),
    'canonical_token_ledgers_scanned':sum(p.name=='token_usage.jsonl' for p in files),
    'sdk_duration_available':sum(r['student_sdk_seconds']!='' for r in rows),
    'student_files_with_request_level_usage_ids':sum(r['cli_calls_with_usage']!='' for r in rows),
    'student_wall_available':sum(r['student_wall_seconds']!='' for r in rows),
    'method':'Exact original attempt-table trajectory/session join or explicit adjacent proxy student/solve route; explicit Bridge ledger preferred when available. Compression suffix normalized. Sum reported CLI delta fields, never cumulative totals or SDK fee estimates. Native early versions can have multiple usage updates and SDK requests within one CLI turn: report events, turns and request IDs separately; missing request-level attribution remains blank. Public copies excluded; file rows cannot simply be summed as independent cost.',
    'table':str(output),'all_roles_ledger_session_rows':len(ledger_rows),
    'all_roles_table':str(OUT/'audit/historical_cli_usage_by_session.csv')}
(OUT/'config/historical_cost_recovery.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
