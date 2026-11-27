import json
from pathlib import Path
import pyarrow.parquet as pq

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
source=json.loads((OUT/'config/development_sources.json').read_text())
def clip(value,n):
    if len(value)<=n:return value
    return value[:n]+f'\n[TRUNCATED: {len(value)-n} original characters omitted; source file retained]'

package=[]
for item in source:
    d=json.loads(Path(item['file']).read_text());index=d['index']
    record={'source_id':d['source_id'],'task':index['task'],'group':index['group'],'round':index['round'],
        'original_trajectory':index['path'],'patch_bytes':index['patch_bytes'],
        'formal_evaluation':{k:v for k,v in d.get('formal_evaluation',{}).items() if k in ('reward','exit_code','stderr_tail','f2p_total','f2p_passed','p2p_total','p2p_passed','f2p','p2p')},
        'student_final':d.get('metadata',{}).get('ResultMessage',{}).get('result',''),
        'events':[],'hints':[]}
    for e in d['events']:
        raw=e['record'];blocks=raw.get('message',{}).get('content',[])
        if isinstance(blocks,str):blocks=[{'text':blocks}]
        keep=[]
        for b in blocks:
            if not isinstance(b,dict):continue
            b={k:v for k,v in b.items() if k in ('type','name','input','content','text','is_error','tool_use_id','id')}
            # Preserve exact strings within a fixed shared cap, without semantic labels.
            for k,v in list(b.items()):
                if isinstance(v,str):b[k]=clip(v,1100)
                elif isinstance(v,dict):b[k]={key:clip(val,1800) if isinstance(val,str) else val for key,val in v.items()}
            keep.append(b)
        record['events'].append({'event':e['event'],'agent':e['agent'],'type':raw.get('type'),'content':keep})
    if index['group']!='B':
        group=index['group'];rnd=index['round']
        for name,hint in d.get('available_hint_archive',d.get('actual_hints',{})).items():
            if name=='full_hint' or (f'_{group}/hint_gen/' in name and f'hint_compact_r{rnd}.md' in name):
                record['hints'].append({'path':hint['path'],'text':clip(hint['text'],6000)})
    online=Path(index['path']).parent/'online_teacher_events.json'
    if online.is_file():record['online_teacher_events']=json.loads(online.read_text())
    record['student_patch']=clip(d.get('student_patch') or '',8000)
    package.append(record)
raw=json.dumps(package,ensure_ascii=False,separators=(',',':'))
assert len(raw)<680000,len(raw)
(OUT/'evidence/development_input.json').write_text(raw+'\n')
common='''Research data restrictions: You receive only the fixed Development cohort D01-D08, not Selection or Test information. All events are historical observations; their order and tool results are evidence. A truncated string does not establish an unobserved result. Do not access files or external tools. Output in English. Do not produce a benchmark solution, exact patch, hidden-test recipe, or task-specific answer to be copied. Treat formal success separately from partial pass, empty patch, technical interruption, and refusal. Identify transferable knowledge and limitations without assuming improvement. Keep this intermediate analysis at most 2200 words. Cite source IDs and event numbers.\n'''
instructions={
'K1':'''Direct raw trajectory distillation baseline. Read each supplied raw trajectory in its chronological text form. Write an ordinary prose summary of reusable lessons, teacher knowledge and observable adoption, effective verification, failures, and caveats. Include successful, failed and partial attempts. Do not build cross-trajectory state tables, explicit state alignment units or semantic-subgoal alignment. Conclude with candidate reusable knowledge, using the same evidence.\n''',
'K2':'''State-aligned trajectory learning. First turn the supplied events into concise evidence-grounded state transition units: inferred semantic subgoal (explicitly mark inference), observed code/program state, operation and affected module/behavior, tool return, visible tests/failure, actual teacher hint, subsequent repair, and verification. Align across trajectories by functional goal/behavior constraint/test category, never equal time index. Separate observed changes from inferred labels. Analyze implementation-independent shared constraints, success/failure differences, effective repairs, method applicability/complementarity and incidental operations. Include an explicit compact alignment table and evidence links. Do not replace this with ordinary full-text summarization. Conclude with candidate reusable knowledge and unsupported hypotheses.\n'''}
for k,instruction in instructions.items():
    prompt=common+instruction+'\nFIXED RAW DEVELOPMENT EVIDENCE:\n'+raw
    assert len(prompt)<=700000
    (OUT/'config'/f'{k}_analysis_prompt.txt').write_text(prompt)
rows=pq.read_table('/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',columns=['instance_id','problem_statement']).to_pylist()
descriptions=[x for x in rows if x['instance_id'] in json.loads((OUT/'config/task_split.json').read_text())['development']]
(OUT/'config/K0_analysis_prompt.txt').write_text('''Teacher-knowledge-only condition. Output in English, at most 2200 words. You may use only the following Development task descriptions, public problem categories and your own general programming knowledge. You have not received and must not invent historical student trajectories, actual patches, Golden Patches, observed tests, Selection or Test tasks. Propose general transferable programming capabilities relevant to these categories, including applicable situations, methods, validation and limitations. Do not solve these tasks, supply task-specific code or guess benchmark answers. Distinguish generic advice from empirical evidence, since you have none.\n'''+json.dumps(descriptions,ensure_ascii=False))
(OUT/'config/extraction_budget.json').write_text(json.dumps({'cohort':source,'raw_characters':len(raw),'per_string_cap':1100,'per_tool_input_string_cap':1800,'student_patch_character_cap':8000,'full_hint_character_cap':6000,'intermediate_words_max':2200,'final_words_max':1000,'calls_per_condition':2,'K1_K2_input_same':True,'input_characters_max_per_call':700000,'preprocessing':'Mechanical field filtering and exact prefix truncation only; identical input JSON bytes for K1 and K2. No semantic labels supplied by monitor.'},indent=2)+'\n')
print('fixed evidence characters',len(raw))
