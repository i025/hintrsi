"""Audit frozen libraries and review completed acquisition runs through the shared SDK."""
import argparse
import datetime
import json
from itertools import combinations
from pathlib import Path
import random
import shutil
import signal
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_03a_capability_acquisition'
PYTHON='/srv/lab-disks/disk2/users/xymo/hint-baseline-run/env/bin/python'
sys.path.insert(0,str(ROOT/'analysis'))
from summarize_run import summarize

CPU_SETS=[list(range(32,40)),list(range(40,48)),list(range(64,72)),list(range(72,80))]
TOOLS=['Read','Glob','Grep','Write']
OUTPUTS={'library-audit':'library_audit.json','visual':'visual_evaluation.json',
         'technical':'technical_annotation.json','knowledge-comparison':'knowledge_comparison.json'}
BUDGETS={'library-audit':(900,60),'visual':(600,36),'technical':(900,60),
         'knowledge-comparison':(700,40)}
TEXT_SUFFIXES={'.py','.json','.jsonl','.md','.txt','.log','.csv'}

LIBRARY_PROMPT='''You are an independent automated auditor of five frozen transferable Blender capability libraries. This is a pre-test audit, not a knowledge-generation or repair session. Read /app/input_index.json. All library and research evidence inputs are read-only under /evidence. You may write only your audit at /app/library_audit.json. Do not revise any condition, generate a better replacement library, or give a condition an extra validation opportunity.

For every condition inspect its actual public SKILL.md, Python modules, capabilities.json, research_evidence.json, validation_report.json, and the indexed real learning/validation SDK events and executed code/log captures. Verify substantive claims against actual executions rather than trusting reports. A source file being written or an exit code being zero is insufficient evidence that every function or branch executed; inspect reachable calls, outputs and Python exceptions. Evidence from independent evaluators is not a learner action.

Check whether the student-facing library contains complete old scene programs, scene-specific old coordinates, original GT assets, dedicated reference textures, paths that load development GT, or old reconstruction answers. Ordinary numeric defaults, geometric constants, caller-supplied coordinates and parameterized synthetic examples are allowed; constants alone do not establish leakage. Distinguish these from copied old scene-specific values or assets. Developer evidence outside the public library may legitimately contain instance parameters; do not falsely report this as student leakage. Mark genuinely uncertain origin or applicability unknown. Audit actual callable definitions and claimed verification, including failures and unvalidated units, without executing new tests.

Compare substantive methods and knowledge overlap, not text similarity or function count. Distinguish prior knowledge implemented during learning, methods supported by development GT inspection, methods grounded in strategy trajectories, exploration-derived execution evidence, new validation experience, and uncertain attribution. A condition name or teacher claim is not evidence of origin or effectiveness. No final-test result is available and no cross-scene transfer claim can yet be verified. Establish a shared canonical semantic method vocabulary across all five libraries: unify synonymous methods under the same label and definition, while keeping substantive technique differences distinct. Every condition must list canonical_semantic_methods as an array of {canonical_label, definition, status: implemented/validated/unknown, module_functions_and_lines, actual_validation_evidence, origin_evidence, uncertainty}. Label unknown rather than absent when a method cannot be determined. Methods need actual source and execution evidence, not a condition name. These common labels support ten library-pair Jaccard comparisons of evidence-supported methods; this is semantic method overlap, never code-text similarity.

Write English JSON with annotation_kind=automated_model, audit_timing=pre_test, conditions (one entry each containing condition, public_files_inspected, possible_answer_or_asset_leakage, fixed_coordinate_findings, executable_units, verification_claim_audit, unsupported_claims, method_origins, applicability_limits, evidence), canonical_semantic_vocabulary (labels, definitions and actual evidence), substantive_overlap (pairwise methods and differences with citations), unresolved_questions, limitations, and human_rating=null. Each finding needs an exact bundle path and code line, SDK event/tool ID, or execution output. Report concerns and uncertainty; do not silently change or selectively repair a library. Finish after saving the file.
'''

VISUAL_PROMPT='''You are an independent automated visual evaluator, not a human rater. You receive exactly two real images: Reference image and Candidate reconstruction. Inspect the actual images. No experiment condition, capability library, prior score, desired outcome, GT implementation, or other candidate is provided.

Evaluate fidelity to the depicted reference rather than visual attractiveness. Independently identify visible objects and important differences in their relative positions, orientations, proportions, spatial layout and occlusion; materials, texture direction/scale/coverage and appearance; visible geometry and connections; camera/composition; lighting and shadows. Do not assume any particular object or defect exists. Identify objects and normalized image regions [left, top, right, bottom] for your observations. Separate visible evidence from uncertainty about hidden surfaces, absolute scale, symmetry, true contact and other properties that RGB cannot establish. Do not penalize an unobservable GT difference or invent a 3D measurement.

Write /app/visual_evaluation.json as English JSON with annotation_kind=automated_model, overall_fidelity_estimate_0_100 (a coarse optional estimate or null), scene_description, visible_objects, spatial_relations_and_orientation, proportions_and_occlusion, materials_and_texture, visible_geometry, camera_and_composition, lighting_and_shadows, objects_regions (each with object, region, observation, evidence_image, severity, priority, confidence), most_important_visible_defects, uncertainty, limitations, and human_rating=null. Dimension entries must contain observations and image evidence; a scalar score is not the sole conclusion. Do not infer learning, condition effects or hidden model reasoning from the images. Finish after writing the file.
'''

TECHNICAL_PROMPT='''You are an automated posthoc technical and capability-adoption annotator. All students have finished and their libraries were frozen before testing. Read /app/input_index.json, then inspect the indexed evidence read-only under /evidence. Do not modify a reconstruction, library or evaluation, and do not send feedback to a student. The reference and delivered candidate are actual image inputs.

The evidence contains real SDK events, original tool calls/results, executed Blender source captures and stdout/stderr, final delivered source, independently extracted scene states and reproduction records, the actually available public capability library (or explicit none for the base student), and GT semantic/instance data and actual GT scene state. Use the index to select relevant files instead of attempting to read every large state at once. Preserve the distinction between student observations and evaluator products: posthoc state extraction, independent regeneration, mask measurements, auxiliary views and geometry checks are evaluator actions unless the student's actual SDK trace demonstrates its own corresponding action.

SKILL.md was supplied verbatim in the initial model prompt for each library condition, and the optional frozen public library was mounted read-only; the base student had neither. Inspect student_initial_prompt.txt and initial_model_input.json when present. Distinguish knowledge_present_in_initial_context, a later Read of library files, an actual import, an actual reachable function invocation, manual reimplementation with an explicit student citation, and mere semantic similarity whose source is unknown. Similar methods or code do not establish that knowledge came from the library. Do not require students to call the optional library. For each capability distinguish read, written, actually executed, verified by the student, and retained in delivered code/scene. Cite exact module/function names, full relative source paths and line numbers, SDK event indices/tool IDs, execution capture names and material/object/node names. Reading a library, importing a module, writing a call, or having its file available is not by itself proof of function execution or benefit. Inspect actual reached code, logs and resulting state. An exit code zero can accompany a Python traceback. Preserve bugs, recovery, nonuse and side effects. Inlined or adapted methods need evidence of substantive correspondence rather than matching names. Do not infer hidden reasoning, general knowledge acquisition, or causal benefit from a condition name.

Analyze spatial relationships, identifiable orientation, scale/proportion, occlusion and camera/layout confounding; distinguish 2D consistency from 3D structural plausibility. GT is one valid implementation, not a unique correct program. Do not compute or claim world-position/angle error unless a reliable coordinate frame, scale and semantic correspondence are established. Both GT and student world transforms are provided to inspect relations, not to imply alignment. Hidden and symmetry-ambiguous properties must remain uncertain.

Inspect actual material output connections, object/material bindings, texture coordinates, mapping direction/scale, image resource paths and packed resources; node existence or complexity alone is not adoption or improvement. Record actual visible/reference agreement separately from implementation detail. A texture on a genuine object is not automatically an image-plane shortcut; flag replacement by a full-reference plane only with scene/code evidence.

Propose semantic correspondences needed for later objective projection-mask comparison. Use a semantic_correspondence array. Each item must have gt_instance_ids (an array of real integers), gt_semantic_label, student_object_names (an explicit list of complete mesh or assembly-root names from the actual original student scene state), confidence (high/medium/low/unknown), basis (evidence array), ambiguity (limitation array), and orientation_identifiability (string). Read the actual GT visible-object and instance-statistics records for IDs; never invent an instance ID. Empty roots may represent their real descendant meshes, but must actually exist in state. For unknown or ambiguous repeated/symmetric matches use confidence=unknown and explain the limit; do not force a match. Include all parts only when their semantic assembly membership is supported. Never invent object names or use broad substring unions. High confidence is a proposal for separate deterministic validation, not a completed numeric match or human-reviewed annotation. Disclose that these semantic correspondences are model-proposed and have not been manually verified. Do not fabricate mask or 3D errors.

Write /app/technical_annotation.json as English JSON with annotation_kind=automated_model, run_id and scene_id (copy the actual IDs from input_index.json), capability_availability (including knowledge_present_in_initial_context), adoption (each entry with unit/module/function, provenance_category: library_read/import_only/actual_invocation/explicitly_cited_reimplementation/semantic_similarity_origin_unknown/unknown, phases read/written/executed/verified/retained/unknown, actual_call_evidence, modified_or_inlined, observed_outcome, attribution_uncertainty), nonuse, methods_actually_executed, student_verification, failures_and_recovery, side_effects, spatial_and_orientation_analysis, appearance_and_resource_analysis, geometry_analysis, semantic_correspondence (gt_instance_ids, gt_semantic_label, student_object_names, confidence, basis, ambiguity, orientation_identifiability), evaluator_only_evidence, unsupported_or_unknown_claims, limitations, and human_rating=null. Cite evidence for every substantive statement. Finish after saving.
'''

COMPARISON_PROMPT='''You are an automated posthoc knowledge-comparison researcher. Read /app/input_index.json. All libraries and completed student outputs are frozen. You may inspect read-only public libraries, their actual research/validation evidence, pre-test audit, all anonymous visual reviews, all technical/adoption annotations, deterministic evaluation records, and original execution evidence through the indexed bundles. This is analysis only; do not modify knowledge or student results.

Compare the five libraries by substantive technical methods, applicability, verification, failure boundaries, and actual knowledge origins. Separate prior knowledge concretized by implementation from development-GT-derived implementation facts, ordinary strategy-trajectory evidence, active-exploration execution experience, and new validation discoveries. Source labels alone do not prove origin, novelty or causal necessity. Return canonical_semantic_vocabulary and, for each condition, canonical_semantic_methods: {canonical_label, definition, status: implemented/validated/unknown, module_functions_and_lines, actual_validation_evidence, origin_evidence, uncertainty}. Unify genuine synonyms across all libraries using the same canonical label; keep materially different techniques separate. Unknown is not absence. These actual semantic labels support ten pairwise library Jaccard comparisons, not code-text similarity. Retain links to the pre-test auditor's labels and explain any evidence-supported relabeling. Identify overlap and redundancy with evidence-supported semantic method comparisons rather than code-text similarity, number of functions or library length.

For the completed paired tasks, assess actual use/nonuse, execution versus mere mention/import, observable outcomes and side effects. All library conditions had the full SKILL text in their initial prompt; knowledge presence is different from library Read, import, an actual reached function call, explicitly cited hand reimplementation, or semantic similarity with unknown origin. Do not label the latter as proven learned-library adoption. Compare A1 vs A0, A3 vs A2, A4 vs A1, A5 vs A3 and A5 vs A4. Preserve mixed and negative results. Distinguish independent visual judgments, measured technical facts, semantic correspondence uncertainty and interpretation. A better scalar image score does not prove improved 3D structure. Never treat evaluator-generated checks as a student capability. Input amounts, hint/library lengths and actual model costs may differ; note confounds. One capability-acquisition round on a few tasks does not establish persistent recursive improvement, statistical significance, or long-term capability growth. Automated judges share the fixed base model and can have correlated errors. Human ratings are unavailable.

Write /app/knowledge_comparison.json as English JSON with annotation_kind=automated_model, canonical_semantic_vocabulary, libraries (condition, canonical_semantic_methods, substantive_methods, origins, validations, limits), pairwise_method_overlap_and_differences, prescribed_contrasts (each with paired_task_evidence, actual_adoption, spatial_outcomes, appearance_outcomes, geometry_outcomes, side_effects, uncertainty), complementary_knowledge_cases, redundancy_cases, prior_knowledge_vs_observed_experience, unsupported_transfer_claims, interpretation_limits, evidence_index, and human_rating=null. Use exact paths and recorded events. Unknown evidence remains unknown. Finish after saving the file.
'''
PROMPTS={'library-audit':LIBRARY_PROMPT,'visual':VISUAL_PROMPT,'technical':TECHNICAL_PROMPT,
         'knowledge-comparison':COMPARISON_PROMPT}


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def copied(source,target,provenance):
    if source.is_file():
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,target)
        provenance.append({'source':str(source),'bundle_path':str(target),'bytes':target.stat().st_size})


def text_tree(source,target,provenance):
    for path in sorted(source.rglob('*')):
        if path.is_file() and not path.is_symlink() and '.git' not in path.parts and '__pycache__' not in path.parts and path.name!='auth.json' and path.suffix in TEXT_SUFFIXES:
            copied(path,target/path.relative_to(source),provenance)


def test_jobs():
    return json.loads((EXP/'configs/frozen_test_order.json').read_text())['jobs']


def require_students_ended():
    assert (EXP/'configs/frozen_libraries.json').exists(),'Libraries must be frozen before posthoc review.'
    for job in test_jobs():
        status=json.loads((EXP/'runs'/job['id']/'status.json').read_text())
        assert status.get('finished_at') and status.get('owned_processes_stopped'),job['id']+' is not finished.'


def freeze_blind_order():
    path=EXP/'configs/acquisition_review_blind_order.json'
    if path.exists():return json.loads(path.read_text())
    split=json.loads((EXP/'configs/data_split.json').read_text())
    ids=[scene['id']+'-A'+str(condition) for scene in split['test'] for condition in range(6)]
    random.Random(2026112803).shuffle(ids)
    order=[{'anonymous_id':'AV'+str(i+1).zfill(3),'run':run} for i,run in enumerate(ids)]
    write(path,order)
    return order


def session_file(stage,mounts=None,visual=False):
    path=EXP/'configs'/('acquisition_review_'+stage+'.json')
    write(path,{'role':'visual_evaluator' if visual else 'posthoc_annotator','tools':['Read','Write'] if visual else TOOLS,
                'initial_images':[{'path':'/app/reference.png','label':'Reference image'},
                                  {'path':'/app/final.png','label':'Candidate reconstruction'}] if stage in ('visual','technical') else [],
                'readonly_mounts':mounts or [],'hint_enabled':False,'persistent_capability_enabled':False,
                'online_teacher_enabled':False})
    return path


def prompt_file(stage):
    path=EXP/'prompts'/('acquisition_review_'+stage+'.txt')
    path.parent.mkdir(parents=True,exist_ok=True);path.write_text(PROMPTS[stage])
    return path


def library_bundle():
    frozen=json.loads((EXP/'configs/frozen_libraries.json').read_text())
    bundle=EXP/'acquisition_review_inputs/library_evidence';provenance=[];index=[]
    for row in frozen['libraries']:
        condition=row['condition'];target=bundle/condition
        text_tree(EXP/'libraries'/condition,target/'public_library',provenance)
        for phase in ('learning','validation'):
            run=EXP/phase/condition
            state=json.loads((run/'status.json').read_text())
            assert state.get('finished_at') and state.get('owned_processes_stopped'),'Learning and validation must end before library review.'
            summarize(run)
            for name in ('research_evidence.json','validation_report.json','source_policy.txt'):
                copied(run/'workspace'/name,target/phase/name,provenance)
            for name in ('sdk_events.json','evidence_index.json'):
                copied(run/'analysis'/name,target/phase/name,provenance)
            for capture in sorted((run/'capture').glob('blender_*')):
                text_tree(capture,target/phase/'executions'/capture.name,provenance)
        index.append({'condition':condition,'public_library':'/evidence/'+condition+'/public_library',
                      'learning_evidence':'/evidence/'+condition+'/learning',
                      'validation_evidence':'/evidence/'+condition+'/validation','frozen_record':row})
    write(bundle/'index.json',index);write(bundle/'provenance.json',provenance)
    return bundle,index


def library_audit_jobs():
    assert not list((EXP/'runs').glob('*/status.json')),'The library audit is prespecified for before student testing.'
    bundle,index=library_bundle()
    seed=EXP/'acquisition_review_inputs/library_audit';seed.mkdir(parents=True,exist_ok=True)
    write(seed/'input_index.json',{'libraries':index,'read_only_evidence':'/evidence/index.json',
          'scope':'Pre-test audit only; no repairs, new tests or final-test results.'})
    reference=Path(json.loads((EXP/'configs/data_split.json').read_text())['development'][0]['reference'])
    config=session_file('library-audit',[{'source':str(bundle),'target':'/evidence'}])
    return [{'id':'AUDIT','checkpoint':str(seed),'image':str(reference),'prompt':str(prompt_file('library-audit')),'session':str(config)}]


def visual_jobs():
    require_students_ended();jobs=[];missing=[]
    config=session_file('visual',visual=True);prompt=prompt_file('visual')
    for row in freeze_blind_order():
        workspace=EXP/'runs'/row['run']/'workspace'
        if not (workspace/'final.png').exists():
            missing.append({'run':row['run'],'anonymous_id':row['anonymous_id'],'reason':'No delivered final.png; no fabricated candidate.'});continue
        seed=EXP/'acquisition_review_inputs/visual'/row['anonymous_id'];seed.mkdir(parents=True,exist_ok=True)
        for name in ('reference.png','final.png'):shutil.copy2(workspace/name,seed/name)
        jobs.append({'id':row['anonymous_id'],'checkpoint':str(seed),'image':str(seed/'reference.png'),
                     'prompt':str(prompt),'session':str(config)})
    write(EXP/'analysis/acquisition_review_visual_missing.json',missing)
    return jobs


def technical_jobs():
    require_students_ended();jobs=[]
    scenes={row['id']:row for row in json.loads((EXP/'configs/data_split.json').read_text())['test']}
    for job in test_jobs():
        run=EXP/'runs'/job['id'];workspace=run/'workspace'
        if not (workspace/'final.png').exists():continue
        summarize(run)
        task=run.name.rsplit('-',1)[0];condition=run.name.rsplit('-',1)[1];scene=scenes[task]
        bundle=EXP/'acquisition_review_inputs/technical_evidence'/run.name;provenance=[]
        for name in ('sdk_events.json','evidence_index.json'):copied(run/'analysis'/name,bundle/name,provenance)
        copied(run/'inputs/prompt.txt',bundle/'student_initial_prompt.txt',provenance)
        request_rows=[json.loads(line) for line in (run/'bridge/model_requests.jsonl').read_text().splitlines()]
        if request_rows:
            request_id=request_rows[0]['request_id']
            copied(run/'bridge'/request_id/'model_input.json',bundle/'initial_model_input.json',provenance)
            copied(run/'bridge'/request_id/'image_attachments.json',bundle/'initial_model_image_associations.json',provenance)
        text_tree(workspace,bundle/'final_source',provenance)
        for capture in sorted((run/'capture').glob('blender_*')):
            text_tree(capture,bundle/'executions'/capture.name,provenance)
        text_tree(run/'analysis/technical',bundle/'independent_evaluation',provenance)
        for name in ('GT.json','objects_in_view.json','metadata.json','instance_segmentation.png'):
            copied(Path(scene['directory'])/name,bundle/'reference_gt'/name,provenance)
        gt_derived=EXP/'data_preparation/new_scene_validation'/task
        for name in ('reference_instance_statistics.json','full_state.json'):
            copied(gt_derived/name,bundle/'reference_gt'/name,provenance)
        if condition!='A0':text_tree(EXP/'libraries'/condition,bundle/'available_library',provenance)
        index={'run':run.name,'scene_id':task,'condition':condition,'student_events':'/evidence/sdk_events.json',
               'student_evidence_index':'/evidence/evidence_index.json','student_initial_context':'/evidence/student_initial_prompt.txt',
               'actual_initial_model_request':'/evidence/initial_model_input.json','delivered_source':'/evidence/final_source',
               'actual_student_executions':'/evidence/executions','independent_evaluation':'/evidence/independent_evaluation',
               'reference_gt':'/evidence/reference_gt','library':'none' if condition=='A0' else '/evidence/available_library',
               'interpretation':'Independent evaluation records are not student actions; GT/student world coordinates are not automatically aligned.',
               'provenance':'/evidence/provenance.json'}
        write(bundle/'index.json',index);write(bundle/'provenance.json',provenance)
        seed=EXP/'acquisition_review_inputs/technical'/run.name;seed.mkdir(parents=True,exist_ok=True)
        for name in ('reference.png','final.png'):shutil.copy2(workspace/name,seed/name)
        write(seed/'input_index.json',index)
        config=EXP/'configs'/('acquisition_review_technical_'+run.name+'.json')
        common=session_file('technical',[{'source':str(bundle),'target':'/evidence'}])
        shutil.copy2(common,config)
        jobs.append({'id':run.name,'checkpoint':str(seed),'image':str(seed/'reference.png'),
                     'prompt':str(prompt_file('technical')),'session':str(config)})
    return jobs


def comparison_jobs():
    require_students_ended()
    for stage in ('visual','technical'):
        for status_path in (EXP/'acquisition_reviews'/stage).glob('*/status.json'):
            status=json.loads(status_path.read_text())
            assert status.get('finished_at') and status.get('owned_processes_stopped'),'Earlier review sessions are still running.'
    libraries,index=library_bundle();reviews=EXP/'acquisition_review_inputs/comparison_reviews';provenance=[];results=[]
    order={row['run']:row['anonymous_id'] for row in freeze_blind_order()}
    for job in test_jobs():
        run=job['id'];anonymous=order[run];record={'run':run,'anonymous_id':anonymous}
        for stage,name,output in [('visual',anonymous,'visual_evaluation.json'),('technical',run,'technical_annotation.json')]:
            source=EXP/'acquisition_reviews'/stage/name/'workspace'/output
            copied(source,reviews/run/output,provenance)
            record[stage]='/reviews/'+run+'/'+output if source.exists() else 'unavailable'
        copied(EXP/'runs'/run/'analysis/technical/result.json',reviews/run/'deterministic_result.json',provenance)
        results.append(record)
    copied(EXP/'acquisition_reviews/library-audit/AUDIT/workspace/library_audit.json',reviews/'library_audit.json',provenance)
    write(reviews/'provenance.json',provenance)
    seed=EXP/'acquisition_review_inputs/knowledge_comparison';seed.mkdir(parents=True,exist_ok=True)
    write(seed/'input_index.json',{'libraries':index,'library_prefix_note':'Library evidence uses /evidence as in the pre-test audit.',
          'runs':results,'pre_test_audit':'/reviews/library_audit.json',
          'actual_technical_evidence':'/technical_evidence/<run>/index.json',
          'technical_prefix_note':'Within each run index, replace /evidence/ with /technical_evidence/<run>/ when following its paths.'})
    mounts=[{'source':str(libraries),'target':'/evidence'},{'source':str(reviews),'target':'/reviews'},
            {'source':str(EXP/'acquisition_review_inputs/technical_evidence'),'target':'/technical_evidence'}]
    config=session_file('knowledge-comparison',mounts)
    reference=json.loads((EXP/'configs/data_split.json').read_text())['development'][0]['reference']
    return [{'id':'COMPARISON','checkpoint':str(seed),'image':reference,
             'prompt':str(prompt_file('knowledge-comparison')),'session':str(config)}]


def batch(jobs,stage,args):
    queue=list(jobs);active={};completed=[];started=time.time();stop=False
    deadline=json.loads((EXP/'start.json').read_text())['deadline_epoch']
    seconds,calls=BUDGETS[stage]
    if stage in ('library-audit','knowledge-comparison'):workers=1
    else:workers=args.workers
    def interrupted(signum,frame):
        nonlocal stop
        stop=True
    signal.signal(signal.SIGTERM,interrupted);signal.signal(signal.SIGINT,interrupted)
    try:
        while queue or active:
            for lane,(process,job,output) in list(active.items()):
                if process.poll() is not None:
                    completed.append({'run':job['id'],'exit_code':process.returncode,'finished_at':time.time()})
                    output.close();del active[lane];print(json.dumps(completed[-1]),flush=True)
            if time.time()>=deadline-60:stop=True
            if stop:break
            for lane in range(workers):
                if lane in active or not queue:continue
                if time.time()+seconds>=deadline-60:continue
                job=queue.pop(0);target=EXP/'acquisition_reviews'/stage/job['id'];target.mkdir(parents=True)
                argv=[PYTHON,'-u','-B',str(ROOT/'harness/run_sdk_session.py'),'--directory',str(target),
                      '--image',job['image'],'--prompt',job['prompt'],'--session-config',job['session'],
                      '--seconds',str(seconds),'--calls',str(calls),'--port',str(args.base_port+lane),
                      '--cpus',','.join(map(str,CPU_SETS[lane])),'--checkpoint',job['checkpoint']]
                output=(target/'supervisor.log').open('wb')
                process=subprocess.Popen(argv,stdout=output,stderr=subprocess.STDOUT,start_new_session=True)
                active[lane]=(process,job,output)
                print(json.dumps({'launched':job['id'],'stage':stage,'lane':lane,'timestamp':time.time()}),flush=True)
            write(EXP/('acquisition_review_'+stage+'_status.json'),{'started_at':started,'updated_at':time.time(),
                  'active':[row[1]['id'] for row in active.values()],'queued':[row['id'] for row in queue],
                  'completed':completed,'workers':workers,'seconds':seconds,'model_requests':calls})
            if queue and not active and time.time()+seconds>=deadline-60:break
            time.sleep(2)
    finally:
        for process,_,_ in active.values():process.terminate()
        for process,_,output in active.values():process.wait();output.close()
        write(EXP/('acquisition_review_'+stage+'_finished.json'),{'started_at':started,'finished_at':time.time(),
              'completed':completed,'unstarted':[row['id'] for row in queue],'interrupted':stop})


def semantic_overlap():
    comparison=EXP/'acquisition_reviews/knowledge-comparison/COMPARISON/workspace/knowledge_comparison.json'
    audit=EXP/'acquisition_reviews/library-audit/AUDIT/workspace/library_audit.json'
    source=comparison if comparison.exists() else audit
    if not source.exists():return None
    annotation=json.loads(source.read_text())
    entries=annotation.get('libraries',[]) if source==comparison else annotation.get('conditions',[])
    methods={};unknown={}
    for entry in entries:
        condition=entry['condition'];labels=entry.get('canonical_semantic_methods',[])
        methods[condition]={row['canonical_label'] for row in labels if row.get('status') in ('implemented','validated')}
        unknown[condition]=[row['canonical_label'] for row in labels if row.get('status')=='unknown']
    pairs=[]
    for first,second in combinations(sorted(methods),2):
        intersection=methods[first]&methods[second];union=methods[first]|methods[second]
        pairs.append({'conditions':[first,second],'shared_labels':sorted(intersection),'union_labels':sorted(union),
                      'known_methods_jaccard':len(intersection)/len(union) if union else None,
                      'unknown_labels':{first:unknown[first],second:unknown[second]}})
    result={'annotation_source':str(source),'pairs':pairs,'method_sets':{key:sorted(value) for key,value in methods.items()},
            'interpretation':'Jaccard of SDK-annotated canonical semantic methods with implemented/validated evidence. Unknown labels are not absence. No code-text similarity or statistical significance claim.',
            'canonical_semantic_vocabulary':annotation.get('canonical_semantic_vocabulary',[])}
    write(EXP/'analysis/acquisition_review_library_overlap.json',result)
    return result


def summarize_reviews():
    phases={};records=[]
    for stage,filename in OUTPUTS.items():
        requests=0;tokens={};errors=[]
        for run in sorted((EXP/'acquisition_reviews'/stage).glob('*')):
            if not (run/'status.json').exists():continue
            summary=summarize(run);requests+=summary['model_requests']
            for key,value in summary['tokens'].items():tokens[key]=tokens.get(key,0)+value
            errors.extend([{'run':run.name,**error} for error in summary['model_errors']])
            request_rows=[json.loads(line) for line in (run/'bridge/model_requests.jsonl').read_text().splitlines()]
            usage_path=run/'bridge/token_usage.jsonl'
            usage_rows=[json.loads(line) for line in usage_path.read_text().splitlines()] if usage_path.exists() else []
            reported={row['request_id'] for row in usage_rows}
            result=run/'workspace'/filename
            records.append({'stage':stage,'review':run.name,'output':str(result) if result.exists() else None,
                            'status':summary['status'],'model_requests':summary['model_requests'],
                            'tokens':summary['tokens'],'model_errors':summary['model_errors'],
                            'requests_without_usage':[row['request_id'] for row in request_rows if row['request_id'] not in reported],
                            'actual_models':sorted({row['actual_model'] for row in request_rows}),
                            'reasoning_efforts':sorted({row['reasoning_effort'] for row in request_rows})})
        phases[stage]={'model_requests':requests,'tokens':tokens,'model_errors':errors}
    write(EXP/'analysis/acquisition_review_usage.json',{'phases':phases,'sessions':records,'actual_billing_usd':None,
          'billing_note':'Observed token counts are not Codex subscription charges. Cached/reasoning tokens are subsets; missing usage is unknown. No Ofox calls.'})
    semantic_overlap()
    return phases


def offline_check():
    """Validate image/context preparation with synthetic fixtures and no model calls."""
    global EXP
    import base64
    import tempfile
    sys.path.insert(0,str(ROOT/'sdk'))
    from codex_cli_bridge import image_messages
    with tempfile.TemporaryDirectory(prefix='acquisition-review-check-') as temporary:
        directory=Path(temporary)
        first='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC'
        second='iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGNgYPgPAAEDAQAIicLsAAAAAElFTkSuQmCC'
        reference_bytes=base64.b64decode(first);candidate_bytes=base64.b64decode(second)
        messages=[{'role':'user','content':[{'type':'text','text':VISUAL_PROMPT},
                   {'type':'text','text':'Reference image'},{'type':'image','source':{'type':'base64','media_type':'image/png','data':first}},
                   {'type':'text','text':'Candidate reconstruction'},{'type':'image','source':{'type':'base64','media_type':'image/png','data':second}}]}]
        converted,attachments=image_messages(messages,directory)
        assert len(attachments)==2 and all(row['media_type']=='image/png' for row in attachments)
        assert Path(attachments[0]['path']).read_bytes()==reference_bytes
        assert Path(attachments[1]['path']).read_bytes()==candidate_bytes
        assert 'E3' not in VISUAL_PROMPT and 'E4' not in VISUAL_PROMPT
        assert 'chair' not in VISUAL_PROMPT and 'door' not in VISUAL_PROMPT and 'countertop' not in VISUAL_PROMPT
        assert len(converted[0]['content'])==5
        assert all(row['bytes']>50 for row in attachments)
        actual_exp=EXP
        EXP=directory/'experiment_fixture'
        try:
            fixture_jobs=[{'id':'FIXTURE-A'+str(condition)} for condition in range(6)]
            write(EXP/'configs/data_split.json',{'test':[{'id':'FIXTURE'}]})
            write(EXP/'configs/frozen_libraries.json',{'libraries':[]})
            write(EXP/'configs/frozen_test_order.json',{'jobs':fixture_jobs})
            for job in fixture_jobs:
                workspace=EXP/'runs'/job['id']/'workspace';workspace.mkdir(parents=True)
                (workspace/'reference.png').write_bytes(reference_bytes)
                (workspace/'final.png').write_bytes(candidate_bytes)
                write(workspace.parent/'status.json',{'finished_at':1,'owned_processes_stopped':True})
            prepared=visual_jobs()
            assert len(prepared)==6
            for job in prepared:
                config=json.loads(Path(job['session']).read_text())
                assert config['readonly_mounts']==[] and len(config['initial_images'])==2
                assert config['tools']==['Read','Write'] and config['persistent_capability_enabled'] is False
                assert sorted(path.name for path in Path(job['checkpoint']).iterdir())==['final.png','reference.png']
            write(EXP/'runs/FIXTURE-A0/status.json',{'status':'running'})
            try:
                require_students_ended()
                raise RuntimeError('Posthoc execution was not blocked while a student was running.')
            except AssertionError:
                pass
        finally:
            EXP=actual_exp
    report={'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'real_model_calls':0,
            'scope':'Synthetic image-byte transport fixture and prompt/context boundaries, not visual understanding or a research evaluation.',
            'two_ordered_valid_png_attachments':True,'generic_fidelity_prompt_without_target_defects':True,
            'no_condition_library_or_gt_inputs_for_visual':True,'posthoc_stages_require_all_student_supervisors_finished':True,
            'shared_sdk_and_bridge_modified':False}
    write(EXP/'infrastructure/acquisition_review_offline_check.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['freeze','library-audit','visual','technical','knowledge-comparison','summarize','check'])
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--workers',type=int,choices=[1,2,4],default=2)
    parser.add_argument('--base-port',type=int,default=19365)
    parser.add_argument('--run',action='append',help='Review selected IDs after the complete student phase has ended.')
    args=parser.parse_args()
    if args.stage=='freeze':freeze_blind_order()
    elif args.stage=='summarize':print(json.dumps(summarize_reviews()),flush=True)
    elif args.stage=='check':offline_check()
    else:
        jobs={'library-audit':library_audit_jobs,'visual':visual_jobs,'technical':technical_jobs,
              'knowledge-comparison':comparison_jobs}[args.stage]()
        if args.run:jobs=[job for job in jobs if job['id'] in args.run]
        write(EXP/'configs'/('acquisition_review_'+args.stage+'_jobs.json'),jobs)
        if args.prepare_only:print(json.dumps({'stage':args.stage,'prepared':len(jobs),'model_calls':0}),flush=True)
        else:batch(jobs,args.stage,args)
