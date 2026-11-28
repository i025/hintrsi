"""Acquire source-controlled libraries and test new scenes through the existing SDK."""
import argparse
import datetime
import json
from pathlib import Path
import shutil
import signal
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_03a_capability_acquisition'
OLD=ROOT/'experiments/experiment_02_teacher_guided_exploration'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
TOOLS=['Bash','Read','Write','Edit','Glob','Grep']
CPU_SETS=[list(range(32,40)),list(range(40,48)),list(range(64,72)),list(range(72,80))]
SOURCES={
 'A1':'Teacher prior: the common development task descriptions, three reference RGB images and fixed capability goals only. No historical student code, execution, candidate, or full Blender GT is available.',
 'A2':'Strategy-trajectory learning: the common development inputs plus all six E3 strategy-guided runs (three scenes, two repetitions), their actual guidance, source versions, tool events, student scene states and executed observations. No full Blender GT is available.',
 'A3':'Exploration-trajectory learning: the common development inputs plus all six E4 exploration-guided runs (three scenes, two repetitions), their actual guidance, candidate source, executions, observations, comparisons and final decisions. No full Blender GT is available.',
 'A4':'GT-guided learning: the common development inputs plus three complete development Blender GT scenes and their true structured data. Historical student code, execution and candidate results are not available.',
 'A5':'GT plus exploration learning: exactly the same complete development GT as A4 and exactly the same six exploration runs and evidence types as A3. This additional information is the experimental variable; tool permissions and budgets are identical.'}

LEARNING_PROMPT='''You are a capability-acquisition teacher for editable Blender reconstruction. Use only the evidence actually available in this isolated workspace. Distinguish observations, technical hypotheses, prior knowledge, execution evidence, and untested transfer claims. Reference implementation is not a unique correct solution; single-image hidden geometry and absolute scale are not identifiable.

Read /app/development_tasks.json and /app/source_policy.txt. The three development reference RGB images are real image inputs and local files. Your common goals are (1) spatial-relational reconstruction: relative position, semantic orientation, proportion, layout, occlusion, and joint camera/layout reasoning; (2) appearance reconstruction: materials, texture coordinates/direction/scale, mappings and separation of illumination from surface properties; (3) auxiliary geometry verification: supports, connected parts, possible intersection and post-repair checking. Do not optimize only tiny support gaps because they are easy to measure.

Information restriction for this condition:
{source_policy}

When historical runs are supplied, inspect every scene and both repetitions. Use /app/trajectory_sources.json, real SDK event indices, executed source captures, saved student states and actual outputs. Distinguish a teacher proposal from code written, code executed, verification actually performed and the final retained method. A rendered candidate does not establish that it was compared or preferred. Do not infer hidden reasoning or credit posthoc evaluator checks as student actions. Do not reuse a visually improved door placement as a general repair if its hinge or opening becomes structurally incoherent. These are general evidence requirements; do not assume a particular historical result is correct.

When development GT is supplied, read /app/development_gt.json for accessible /dev_gt/Sxx/scene.blend paths; host paths in provenance records are not mounted paths. Inspect the actual .blend through Blender queries, including transforms and assemblies, material bindings, node groups, UV/texture coordinates and packed/external textures, camera and lights. Do not infer technique from material names or GT.json alone. You may use /app/gt_inspection/ as an index, but directly query the real Blender files for any GT-derived method you claim. Do not assume original generation code or construction trajectories exist.

Build an English transferable capability library at /app/library/. You may write readable Skill text, executable Blender Python methods and actual analysis/checking tools. All conditions have the same tools and may implement any of these forms. Choose a useful representation and number of units; do not manufacture equal function counts. Each unit must state: Capability Name; Applicable Conditions; Problem and Technical Hypotheses; Executable Method; Verification Method; Failure Conditions and Side Effects; Evidence and Knowledge Origin. Use /app/library/SKILL.md as the entry point. Put reusable implementation in .py files, with a small machine-readable /app/library/capabilities.json listing modules and entry points. The public library may contain only .md, .py and .json files, at most 6,000 natural-language words, at most 1,200 nonblank Python lines and 120 KiB total. No scene files, images, original assets, scene-specific coordinates, dedicated textures, copied scene programs, historical answers, or files that merely load development GT. Examples must be synthetic and parameterized. Evidence with development-specific numbers belongs ONLY in /app/research_evidence.json, outside the public library.

At least make any claimed executable method callable; document required inputs, outputs and uncertainty. For support methods distinguish positive gap, near-zero, possible penetration and unknown support, and distinguish assembly connectivity from support. AABB overlap or a near-zero measurement is not proof of physical contact. These are interpretation boundaries, not a required algorithm. Material complexity or node count is not evidence of visual improvement.

You may execute Blender and create your own small checks within this generation budget. A later equal-budget validation stage will provide one selection reference RGB; it will not provide selection GT or final test results. Preserve abandoned candidates and actual checks outside library/. Do not claim cross-scene improvement before independent testing. Write /app/research_evidence.json with source-specific observations, citations, actually executed tests, unknowns, rejected candidates and claimed unit origins. Deliver the actual files, not only advice. Finish after creating them. Budget: 20 minutes, at most 60 model requests. Blender 5.2.2, CPU with eight threads; writable workspace /app.
'''

VALIDATION_PROMPT='''Validate and, if necessary, revise your own candidate capability library before independent testing. This is a new SDK session; read /app/library/SKILL.md, capabilities.json and /app/research_evidence.json. Your original information boundary is still /app/source_policy.txt. Do not access unavailable historical trajectories or GT.

The three development reference images and one held-out selection reference image are provided. Selection GT and final test data are unavailable. Every learning condition has the same 12-minute, 36-model-request validation opportunity and identical Blender/file tools. Use actual Blender executions to check callable methods, applicability and side effects. Create small synthetic tests with known relationships and materials, and test any applicable methods in your own editable probe for the selection reference. You may build a limited selection-scene probe; there is no requirement to finish a full reconstruction. Methods outside your library's supported scope may be explicitly unvalidated rather than fabricated. Do not copy reference image planes as a reconstruction.

Check that spatial changes preserve the distinction between entire assemblies and internal parts and do not optimize only a 2D silhouette while invalidating a hinge/opening/support relation. Inspect actual material output connections, bindings, coordinates and image resources when testing appearance methods; a node merely existing is not evidence it affects the output. Geometry checks must distinguish unknown from absent support, near-zero from proof of contact, and AABB candidates from confirmed intersections. Preserve failures, exceptions, candidates and source revisions; do not claim a test ran just because code was written.

You can repair or remove non-executable candidate units under the same budget as other conditions. Keep unsupported methods marked unvalidated. Retain only student-facing general methods in /app/library/: .md/.py/.json, maximum 6,000 natural-language words, 1,200 nonblank Python lines and 120 KiB total. Keep developer-specific instances, any original GT data, raw evidence, probes and old answers outside this folder. No old scene coordinates, assets or reconstruction programs may enter the student library. Parameterized synthetic examples are allowed.

Write /app/validation_report.json with: tested_units, actual_commands, actual_outputs, selection_probe, failed_or_rejected_candidates, changes, remaining_unvalidated_methods, applicability_and_side_effects, and final_library_files. Cite actual files and observations. Only report verification that really happened. Do not use or request final-test results. Finish after saving the library and report.
'''


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def copy_tree(source,target):
    shutil.copytree(source,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','__pycache__','*.pyc','auth.json'))


def prepare():
    scenes=json.loads((ROOT/'configs/scenes.json').read_text())['scenes']
    tasks=[]
    for s in scenes:
        tasks.append({'id':s['id'],'task':(ROOT/'configs/student_prompt.txt').read_text(),
                      'reference_image':s['id']+'_reference.png','capability_goals':['spatial relations and orientation','appearance and texture','auxiliary geometry verification']})
    budgets={'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':'gpt-6.1-terra','reasoning_effort':'low','generation_seconds':1200,'generation_model_requests':60,'validation_seconds':720,'validation_model_requests':36,'library_words':6000,'library_nonblank_python_lines':1200,'library_bytes':120*1024,'student_seconds':1500,'student_model_requests':120,'student_workers':4,'learning_workers':2,'cpu_sets':CPU_SETS,'threads':8,'render_resolution':[640,360],'selection_feedback_into_final_tests':False,'online_teacher':False,'skill_autoload':False,'persistent_library_mount':'/capabilities','model_cost_note':'Actual Codex USD charge is unknown; observed token usage is recorded. No Ofox calls.'}
    write(EXP/'configs/learning_budget.json',budgets)
    (EXP/'prompts/validation.txt').write_text(VALIDATION_PROMPT)
    (EXP/'prompts/base_student.txt').write_text((ROOT/'configs/formal_prompt.txt').read_text())
    for condition,policy in SOURCES.items():
        seed=EXP/'learning_inputs'/condition;seed.mkdir(parents=True,exist_ok=True)
        write(seed/'development_tasks.json',tasks);(seed/'source_policy.txt').write_text(policy+'\n')
        for s in scenes:shutil.copy2(Path(s['evaluation_directory'])/'color.png',seed/(s['id']+'_reference.png'))
        images=[{'path':'/app/'+s['id']+'_reference.png','label':'Development reference '+s['id']} for s in scenes]
        mounts=[]
        if condition in ('A2','A3','A5'):
            group='E3' if condition=='A2' else 'E4';records=[]
            for s in scenes:
                for repetition in (1,2):
                    name=s['id']+'-'+group+'-R'+str(repetition);run=OLD/'runs'/name;dest=seed/'trajectories'/name
                    for folder in ('workspace','capture'):copy_tree(run/folder,dest/folder)
                    evidence=dest/'analysis';evidence.mkdir(exist_ok=True)
                    for f in ('sdk_events.json','evidence_index.json'):shutil.copy2(run/'analysis'/f,evidence/f)
                    state=run/'analysis/technical/capture/final_state.json'
                    if state.exists():shutil.copy2(state,evidence/'student_scene_state.json')
                    diagnosis=json.loads((OLD/'hints'/(s['id']+'.json')).read_text())
                    (dest/'actual_guidance.txt').write_text(diagnosis['hints'][group])
                    records.append({'scene':s['id'],'repetition':repetition,'condition':group,'path':'/app/trajectories/'+name,'source':str(run),'reference':'/app/'+s['id']+'_reference.png','information':'Actual student code, execution captures, SDK events and student scene state, not full GT or other groups.'})
            write(seed/'trajectory_sources.json',records)
        if condition in ('A4','A5'):
            mounts=[{'source':s['evaluation_directory'],'target':'/dev_gt/'+s['id']} for s in scenes]
            gt_index=EXP/'data_preparation/development_gt'
            if gt_index.exists():copy_tree(gt_index,seed/'gt_inspection')
            write(seed/'development_gt.json',[{'scene':s['id'],'directory':'/dev_gt/'+s['id'],'scene':'/dev_gt/'+s['id']+'/scene.blend'} for s in scenes])
        session={'role':'teacher','condition':condition,'tools':TOOLS,'initial_images':images,'readonly_mounts':mounts,'hint_enabled':False,'persistent_capability_enabled':False}
        write(EXP/'configs'/(condition+'-learning.json'),session)
        (EXP/'prompts'/(condition+'-learning.txt')).write_text(LEARNING_PROMPT.format(source_policy=policy))
    print('Prepared five information conditions and common pre-learning budgets.',flush=True)


def learning_jobs(conditions):
    return [{'id':a,'checkpoint':str(EXP/'learning_inputs'/a),'image':str(EXP/'learning_inputs'/a/'S01_reference.png'),
             'prompt':str(EXP/'prompts'/(a+'-learning.txt')),'session':str(EXP/'configs'/(a+'-learning.json'))} for a in conditions]


def validation_jobs():
    split=json.loads((EXP/'configs/data_split.json').read_text());selection=split['selection'][0];jobs=[]
    for condition in SOURCES:
        seed=EXP/'validation_inputs'/condition
        copy_tree(EXP/'learning'/condition/'workspace',seed)
        shutil.copy2(selection['reference'],seed/'selection_reference.png')
        session=json.loads((EXP/'configs'/(condition+'-learning.json')).read_text())
        session['role']='teacher'
        session['task_kind']='capability_validation'
        session['initial_images'].append({'path':'/app/selection_reference.png','label':'Selection reference RGB; selection GT unavailable'})
        write(EXP/'configs'/(condition+'-validation.json'),session)
        jobs.append({'id':condition,'checkpoint':str(seed),'image':str(seed/'S01_reference.png'),
                     'prompt':str(EXP/'prompts/validation.txt'),'session':str(EXP/'configs'/(condition+'-validation.json'))})
    return jobs


def freeze():
    records=[]
    for condition in SOURCES:
        workspace=EXP/'validation'/condition/'workspace';source=workspace/'library';target=EXP/'libraries'/condition
        copy_tree(source,target)
        paths=[p for p in target.rglob('*') if p.is_file()]
        words=sum(len(p.read_text().split()) for p in paths if p.suffix in ('.md','.json'))
        lines=sum(sum(bool(line.strip()) for line in p.read_text().splitlines()) for p in paths if p.suffix=='.py')
        size=sum(p.stat().st_size for p in paths)
        eligible=(target/'SKILL.md').exists() and (target/'capabilities.json').exists() and words<=6000 and lines<=1200 and size<=120*1024 and all(p.suffix in ('.md','.py','.json') for p in paths)
        for p in paths:
            if p.suffix=='.py':compile(p.read_text(),str(p),'exec')
        record={'condition':condition,'words':words,'nonblank_python_lines':lines,'bytes':size,'eligible':eligible,'files':[str(p.relative_to(target)) for p in paths],'validation_report':str(workspace/'validation_report.json'),'source_policy':SOURCES[condition]}
        records.append(record)
    write(EXP/'configs/frozen_libraries.json',{'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'libraries':records,'test_results_used':False})
    assert all(r['eligible'] for r in records),'A library exceeds the common pre-test rule; inspect actual record before testing.'
    print('Froze all five capability libraries.',flush=True)


def with_capability_library(prompt, library):
    if library is not None:
        prompt+='\nFrozen general capability knowledge:\n'+(Path(library)/'SKILL.md').read_text()+'\n\nA frozen general capability library is available read-only at /capabilities. Its entry point is /capabilities/SKILL.md. You may inspect and use its documented methods when applicable, or choose your own methods. It contains no task-specific teacher feedback or reference scene assets. Keep any dependency needed to reproduce your final source with the delivered workspace.\n'
    return prompt


def student_jobs():
    split=json.loads((EXP/'configs/data_split.json').read_text());scenes=split['test'];jobs=[]
    base=(EXP/'prompts/base_student.txt').read_text()
    for offset in range(6):
        for i,scene in enumerate(scenes):
            condition='A'+str((offset+i)%6);name=scene['id']+'-'+condition
            prompt=base
            mounts=[]
            if condition!='A0':
                prompt=with_capability_library(prompt,EXP/'libraries'/condition)
                mounts=[{'source':str(EXP/'libraries'/condition),'target':'/capabilities'}]
            path=EXP/'prompts'/(condition+'-student.txt');path.write_text(prompt)
            config=EXP/'configs'/(condition+'-student.json')
            write(config,{'role':'student','condition':condition,'tools':TOOLS,'readonly_mounts':mounts,'hint_enabled':False,'persistent_capability_enabled':condition!='A0','online_teacher_enabled':False,'initial_images':[{'path':'/app/reference.png','label':'Reference image'}]})
            jobs.append({'id':name,'image':scene['reference'],'prompt':str(path),'session':str(config)})
    write(EXP/'configs/frozen_test_order.json',{'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'jobs':jobs,'source':'Prespecified balanced interleaving of four new tasks and all six groups; no test outcome used.'})
    return jobs


def batch(jobs,label,directory,seconds,calls,workers=2):
    queue=list(jobs);active={};completed=[];started=time.time();stop=False
    deadline=json.loads((EXP/'start.json').read_text())['deadline_epoch']
    def interrupted(signum,frame):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        while queue or active:
            for lane,(process,job,output) in list(active.items()):
                if process.poll() is not None:
                    completed.append({'run':job['id'],'exit_code':process.returncode,'finished_at':time.time()});output.close();del active[lane]
                    print(json.dumps(completed[-1]),flush=True)
            if (EXP/'STOP').exists() or time.time()>=deadline-3600:stop=True
            if stop:break
            for lane in range(workers):
                if lane in active or not queue:continue
                if time.time()+seconds>=deadline-3600:continue
                job=queue.pop(0);target=directory/job['id'];target.mkdir(parents=True)
                argv=[PYTHON,'-u','-B',str(ROOT/'harness/run_sdk_session.py'),'--directory',str(target),'--image',job['image'],'--prompt',job['prompt'],'--session-config',job['session'],'--seconds',str(seconds),'--calls',str(calls),'--port',str(19165+lane),'--cpus',','.join(map(str,CPU_SETS[lane]))]
                if job.get('checkpoint'):argv+=['--checkpoint',job['checkpoint']]
                output=(target/'supervisor.log').open('wb');process=subprocess.Popen(argv,stdout=output,stderr=subprocess.STDOUT,start_new_session=True);active[lane]=(process,job,output)
                print(json.dumps({'launched':job['id'],'phase':label,'lane':lane,'timestamp':time.time()}),flush=True)
            write(EXP/(label+'_status.json'),{'started_at':started,'updated_at':time.time(),'active':[v[1]['id'] for v in active.values()],'queued':[v['id'] for v in queue],'completed':completed,'workers':workers,'seconds':seconds,'calls':calls})
            if queue and not active and time.time()+seconds>=deadline-3600:break
            time.sleep(2)
    finally:
        for process,_,_ in active.values():process.terminate()
        for process,_,output in active.values():process.wait();output.close()
        write(EXP/(label+'_finished.json'),{'started_at':started,'finished_at':time.time(),'completed':completed,'unstarted':[j['id'] for j in queue],'interrupted':stop,'owned_supervisors_stopped':True})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['prepare','learn','validate','freeze','students']);parser.add_argument('--condition',action='append');args=parser.parse_args()
    if args.stage=='prepare':prepare()
    elif args.stage=='learn':batch(learning_jobs(args.condition or list(SOURCES)),'learning',EXP/'learning',1200,60)
    elif args.stage=='validate':batch(validation_jobs(),'validation',EXP/'validation',720,36)
    elif args.stage=='freeze':freeze()
    else:batch(student_jobs(),'students',EXP/'runs',1500,120,4)
