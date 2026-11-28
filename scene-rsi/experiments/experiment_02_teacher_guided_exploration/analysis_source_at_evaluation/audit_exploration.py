"""Inspect actual request conditions and the scientific record, without hashes."""
import argparse
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'


def strings(value):
    if isinstance(value,str):yield value
    elif isinstance(value,list):
        for item in value:yield from strings(item)
    elif isinstance(value,dict):
        for item in value.values():yield from strings(item)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repetition',type=int,choices=[1,2])
    args=parser.parse_args()
    records=[];scene_images={};systems=[]
    for run in sorted((EXP/'runs').iterdir()):
        if args.repetition and not run.name.endswith('-R'+str(args.repetition)):continue
        requests=[json.loads(line) for line in (run/'bridge/model_requests.jsonl').read_text().splitlines()]
        first=requests[0];body=first['request'];request_dir=run/'bridge'/first['request_id']
        images=json.loads((request_dir/'image_attachments.json').read_text())
        actual=[Path(row['path']).read_bytes() for row in images]
        scene_images.setdefault(run.name[:3],actual)
        systems.append(body['messages'][0])
        prompt=(run/'inputs/prompt.txt').read_text()
        tools=[tool['function']['name'] for tool in body['tools']]
        commands=[json.loads((run/'bridge'/r['request_id']/'command.json').read_text()) for r in requests]
        expected_model=all(c[c.index('--model')+1]=='gpt-6.1-terra' for c in commands)
        expected_effort=all('model_reasoning_effort="low"' in c for c in commands)
        native=[]
        events=run/'bridge/codex_events.jsonl'
        for line in events.read_text().splitlines():
            row=json.loads(line);event=row['event'];item=event.get('item',{})
            if item.get('type') not in (None,'agent_message','reasoning'):
                native.append({'request_id':row['request_id'],'event':event})
        records.append({'run':run.name,'expected_prompt_in_initial_request':any(prompt in s for s in strings(body['messages'])),
                        'initial_image_count':len(images),'same_initial_image_bytes_within_scene':actual==scene_images[run.name[:3]],
                        'image_media_types':[row['media_type'] for row in images],
                        'tools':tools,'model_command_correct':expected_model,'effort_command_correct':expected_effort,
                        'non_message_native_events':native,'auth_copy_removed':not (run/'backend_home/auth.json').exists(),
                        'session_config':json.loads((run/'inputs/session.json').read_text())})
    teachers=[]
    for run in sorted((EXP/'teachers').iterdir()):
        unchanged=all((run/'workspace'/p.name).read_bytes()==p.read_bytes()
                      for p in (EXP/'checkpoints'/run.name).iterdir() if p.is_file())
        teachers.append({'case':run.name,'checkpoint_files_unchanged':unchanged,
                         'diagnosis_present':(run/'workspace/teacher_diagnosis.json').exists(),
                         'raw_role_metadata':'legacy student route; actual role teacher from session configuration',
                         'auth_copy_removed':not (run/'backend_home/auth.json').exists()})
    result={'runs':records,'teacher_records':teachers,'all_initial_system_messages_identical':all(s==systems[0] for s in systems),
            'no_hash_or_checksum_system':True,'measurement':'Direct inspection of actual prompts, CLI arguments, image contents, tool lists and event logs.',
            'limitation':'CLI request acceptance and recorded model flag establish the requested backend configuration, not independent inspection of provider weights.'}
    (EXP/'analysis').mkdir(exist_ok=True)
    filename='request_condition_audit'+('_R'+str(args.repetition) if args.repetition else '')+'.json'
    (EXP/'analysis'/filename).write_text(json.dumps(result,indent=2))
    print('Audited',len(records),'actual branch inputs; equal system messages:',result['all_initial_system_messages_identical'])


if __name__=='__main__':main()
