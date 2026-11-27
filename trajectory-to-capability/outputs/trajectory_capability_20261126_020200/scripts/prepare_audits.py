import json
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
sources=json.loads((OUT/'config/development_sources.json').read_text())
prompt='''Audit this actual historical student attempt from original files. Output an English evidence report of at most 1800 words. Identify source path and exact agent/event numbers. Report: task goal; actual operations; files/behavior changed; teacher knowledge actually received (the captured actual request takes priority over planned hints); direct evidence of adoption; independent exploration/validation; final outcome including F2P/P2P; stop reason, technical faults, timing and usage limits; transferable versus task-specific experiences; unverified hypotheses. Distinguish formal solved, partial correctness, empty patch, normal algorithmic failure, technical interruption and early refusal. Do not turn a successful trajectory into proof of long-term learning. Teacher advice and agent self-report alone do not prove adoption. State any omitted fields or incomplete evidence. The complete event sequence is supplied below; do not treat absent requests or omitted archives as audited. Do not solve any new task.\n\n'''
for source in sources:
    d=json.loads(Path(source['file']).read_text())
    d.pop('actual_hints',None)
    d['scope']='One development attempt; complete parsed event sequence, actual student patch and formal evaluation.'
    p=Path(d['index']['path']).parent
    for name in ('system_prompt_actual.json','online_teacher_events.json','online_teacher_state.json'):
        f=p/name
        if f.exists():d[name]={'source':str(f),'data':json.loads(f.read_text())}
    path=OUT/'config'/f'audit_{source["source_id"]}_prompt.txt'
    path.write_text(prompt+json.dumps(d,ensure_ascii=False,separators=(',',':')))
    print(source['source_id'],path.stat().st_size)
