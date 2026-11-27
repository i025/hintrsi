import json
from pathlib import Path

HOME=Path('/srv/lab-disks/disk2/users/xymo')
BASE=HOME/'Documents/Codex/2026-11-02/scene-rsi-rsi-1-3d-blender/outputs'
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
jobs=[]
common='''Audit the supplied real Scene RSI records. Output in English, at most 2200 words. Cite exact absolute source files and JSONL event numbers or Python line numbers. Distinguish observed file/code/tool state from model interpretation. Investigate multi-object coverage; material/texture quality; disconnected object parts; position/orientation; camera/lighting/rendering. For each relevant concern distinguish: issue mentioned by teacher, diagnosis supported or unsupported, update targeted or unrelated, student actually adopted update, and verified result. An instruction or student claim is not adoption evidence. Rendering success is not reconstruction quality. No images are attached to this text-only audit: visual observations are recorded teacher/student claims unless backed by numerical geometry/program evidence. Do not infer all experiments from a few images, confuse archive copies with independent attempts, or claim unreviewed files were audited. Separate H/M acceptance rule from true learned capability; note technical failures and limitations.\n'''

def packet(case,title,paths):
    unique=list(dict.fromkeys(p for p in paths if p.is_file()))
    rows=[];budget=650000
    for p in unique:
        try:text=p.read_text()
        except UnicodeError:continue
        cap=min(100000,budget)
        if cap<300:break
        used=text[:cap]
        rows.append({'path':str(p),'original_characters':len(text),'included_characters':len(used),
            'complete':len(text)==len(used),'format':'JSONL: event number is one-based physical line' if p.suffix=='.jsonl' else 'Text/JSON: use actual keys or one-based source line',
            'text':used+(' ['+str(len(text)-len(used))+' remaining characters omitted]' if len(text)>len(used) else '')})
        budget-=len(used)
    data={'case':case,'title':title,'sources':rows,'images_reviewed_in_this_call':False}
    (OUT/'evidence'/f'{case}_scene_packet.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    prompt=OUT/'config'/f'audit_{case}_prompt.txt'
    prompt.write_text(common+json.dumps(data,ensure_ascii=False,separators=(',',':')))
    jobs.append({'case':case,'title':title,'prompt':str(prompt),'files_included':len(rows),'complete_files':sum(x['complete'] for x in rows),'sources':[{k:v for k,v in x.items() if k!='text'} for x in rows]})

stage=BASE/'stagewise_teaching_student_selfcheck_pilot'
for case,task in [('S01','D01'),('S02','T01')]:
    p=stage/'tasks'/task
    paths=[stage/'protocol_freeze.json',p/'state.json',p/'plan.json']
    paths+=sorted(p.glob('stages/*/stage.json'))
    paths+=sorted(p.glob('stages/*/*build/patch.py'))
    paths+=sorted(p.glob('stages/*/*build/stage_events.jsonl'))
    paths += [stage/'transfer/self_check_policy.md',stage/'transfer/lesson_provenance.json',stage/'transfer/freeze.json']
    packet(case,f'Stagewise {task}: five semantic stages, teacher/self-review, actual incremental Blender patches, render events',paths)

human=BASE/'teacher_self_evolution_human_pilot'
paths=[human/'self_modification/M0_to_M1.diff',human/'teachers/M0/teacher.py',human/'teachers/M1/teacher.py']
for task in ['E02_M0_R2','E02_M1_R2']:
    p=human/'tasks'/task
    paths += [p/n for n in ['teacher_context.json','guidance.json','student_input.json','student_decision_1.json','student_decision_2.json','trajectory.jsonl','status.json','build.py','camera.json','selected.json']]
    paths += sorted(p.glob('steps/*/build.py'))+sorted(p.glob('steps/*/stage_events.jsonl'))
packet('S03','One M0 to M1 teacher self-modification and matched E02 R2 guidance/student execution',paths)

v3=BASE/'scene_rsi_v3'
paths=[v3/'meta_traces/round04/decisions.json',v3/'rounds/04/record.json',v3/'candidates/C04/H.diff',v3/'candidates/C04/H/policy.py',v3/'candidates/C04/worker_summary.json']
for task in ['commons_118588033','commons_104864364']:
    p=v3/'results/H04/development'/task/'1'
    paths += [p/n for n in ['build.py','trajectory.jsonl','summary.json','evaluation.json','camera.json','scene_structure.json','selected.json']]
    paths += sorted(p.glob('steps/*/build_stdout.log'))[:3]
packet('S04','V3 round04 camera sign and numerical projection update, accepted H04 and subsequent actual students',paths)

paths=[v3/'meta_traces/round07/decisions.json',v3/'rounds/07/record.json',v3/'rounds/08/record.json',v3/'candidates/C07/M.diff',v3/'candidates/C07/M_program_execution.json',v3/'candidates/C07/M_execution_contract.json',v3/'candidates/C07/M_action_reuse_validation.json',v3/'metrics/M_changed_content_execution_audit.json',v3/'metrics/M07_review.json']
packet('S05','V3 M07 meta-agent update, action evidence and candidate acceptance limitations',paths)

pilot=BASE/'scene_rsi_pilot'
paths=[pilot/'selections.json',pilot/'reports/geometry_relations.csv',pilot/'reports/execution_attempts.csv']
p=pilot/'candidates/r1/scene_rsi_pilot/C1'
paths += [p/n for n in ['diagnostic_observations.json','proposal_result.json','changes.diff','meta_execution.json','evidence_projection.json','validation_v3.json']]
for method in ['C1','C2']:
    directory=pilot/'results/r1/scene_rsi_pilot'/method
    candidates=sorted(directory.rglob('trajectory.jsonl'))
    if candidates:
        p=candidates[0].parent
        paths += [p/n for n in ['trajectory.jsonl','build.py','scene_structure.json','camera.json','evaluation.json','summary.json','record.json']]
packet('S06','Original pilot structured observations, geometry relations, candidate C1/C2 and selection record',paths)

(OUT/'audit/scene_deep_audit_sources.json').write_text(json.dumps(jobs,ensure_ascii=False,indent=2)+'\n')
print(json.dumps([{k:v for k,v in x.items() if k!='sources'} for x in jobs]))
