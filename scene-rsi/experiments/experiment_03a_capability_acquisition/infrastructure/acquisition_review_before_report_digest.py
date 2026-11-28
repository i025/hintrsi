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
from summarize_run import summarize, rows

CPU_SETS=[list(range(32,40)),list(range(40,48)),list(range(64,72)),list(range(72,80))]
TOOLS=['Read','Glob','Grep','Write']
OUTPUTS={'library-audit':'library_audit.json','visual':'visual_evaluation.json',
         'technical':'technical_annotation.json','projection-review':'projection_identity_review.json','projection-followup':'projection_identity_review.json','knowledge-comparison':'knowledge_comparison.json','report':'REPORT_ZH.md'}
BUDGETS={'library-audit':(900,60),'visual':(600,36),'technical':(900,60),
         'knowledge-comparison':(700,40),'projection-review':(600,36),'projection-followup':(240,16),'report':(900,60)}
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

TECHNICAL_PROMPT='''You are an automated posthoc technical and capability-adoption annotator. All students have finished and their libraries were frozen before testing. Read /app/input_index.json, then inspect the indexed evidence read-only under /evidence. Do not modify a reconstruction, library or evaluation, and do not send feedback to a student. The reference is an actual image input; an actually delivered final image is included only when it exists. If final.png is missing, you receive only the real reference, never a substitute candidate. Inspect delivery_status and the actual failed/ended trace. Missing build.py, scene.blend or final.png is a recorded student task outcome, not a reason to exclude the run. Annotate observable stopping, actual nonuse and unknown quality without inventing a visual score or repair. If no student scene exists, semantic_correspondence must be an empty array; do not map GT objects to nonexistent student objects. Distinguish task non-completion from actual SDK/Bridge errors using the recorded evidence.

The evidence contains real SDK events, original tool calls/results, executed Blender source captures and stdout/stderr, final delivered source, independently extracted scene states and reproduction records, the actually available public capability library (or explicit none for the base student), and GT semantic/instance data and actual GT scene state. Use the index to select relevant files instead of attempting to read every large state at once. Start with original_object_inventory and gt_visible_instances to locate real names/IDs, then inspect full state only for details. Each object_inventory.jsonl entry is an actual object record, not a semantic judgment. Its projected bounds and projected bbox center use bottom-up image coordinates and an unclipped bounding box; they are not visible-mask centroids, instance masks or aligned 3D errors. Preserve the distinction between student observations and evaluator products: posthoc state extraction, independent regeneration, mask measurements, auxiliary views and geometry checks are evaluator actions unless the student's actual SDK trace demonstrates its own corresponding action.

SKILL.md was supplied verbatim in the initial model prompt for each library condition, and the optional frozen public library was mounted read-only; the base student had neither. Inspect student_initial_prompt.txt and initial_model_input.json when present. Distinguish knowledge_present_in_initial_context, a later Read of library files, an actual import, an actual reachable function invocation, manual reimplementation with an explicit student citation, and mere semantic similarity whose source is unknown. Similar methods or code do not establish that knowledge came from the library. Do not require students to call the optional library. For each capability distinguish read, written, actually executed, verified by the student, and retained in delivered code/scene. Cite exact module/function names, full relative source paths and line numbers, SDK event indices/tool IDs, execution capture names and material/object/node names. Reading a library, importing a module, writing a call, or having its file available is not by itself proof of function execution or benefit. Inspect actual reached code, logs and resulting state. An exit code zero can accompany a Python traceback. Preserve bugs, recovery, nonuse and side effects. Inlined or adapted methods need evidence of substantive correspondence rather than matching names. Do not infer hidden reasoning, general knowledge acquisition, or causal benefit from a condition name.

Analyze spatial relationships, identifiable orientation, scale/proportion, occlusion and camera/layout confounding; distinguish 2D consistency from 3D structural plausibility. GT is one valid implementation, not a unique correct program. Do not compute or claim world-position/angle error unless a reliable coordinate frame, scale and semantic correspondence are established. Both GT and student world transforms are provided to inspect relations, not to imply alignment. Hidden and symmetry-ambiguous properties must remain uncertain.

Actual rendered PNGs preserved with executed Blender captures are available under executions/*/artifacts/; correlate them with the student tool events before crediting an observation or comparison. Inspect actual material output connections, object/material bindings, texture coordinates, mapping direction/scale, image resource paths and packed resources; node existence or complexity alone is not adoption or improvement. Record actual visible/reference agreement separately from implementation detail. When common_light_comparison provides real images, you may inspect both actual student and GT auxiliary images and settings. They were generated by the independent evaluator, never the student. White-world lighting retains original geometry, materials and camera plus emission and other residual confounds; it is an auxiliary comparison, not proof of appearance improvement. Missing scenes have no auxiliary image and must not receive an invented image or score. A texture on a genuine object is not automatically an image-plane shortcut; flag replacement by a full-reference plane only with scene/code evidence.

Propose semantic correspondences needed for later objective projection-mask comparison. Use a semantic_correspondence array. Each item must have gt_instance_ids (an array of real integers), gt_semantic_label, student_object_names (an explicit list of complete mesh or assembly-root names from the actual original student scene state), confidence (high/medium/low/unknown), basis (evidence array), ambiguity (limitation array), and orientation_identifiability (string). Read the actual GT visible-object and instance-statistics records for IDs; never invent an instance ID. Empty roots may represent their real descendant meshes, but must actually exist in state. For unknown or ambiguous repeated/symmetric matches use confidence=unknown and explain the limit; do not force a match. Include all parts only when their semantic assembly membership is supported. Never invent object names or use broad substring unions. High confidence is a proposal for separate deterministic validation, not a completed numeric match or human-reviewed annotation. Disclose that these semantic correspondences are model-proposed and have not been manually verified. Do not fabricate mask or 3D errors.

Write /app/technical_annotation.json as English JSON with annotation_kind=automated_model, run_id and scene_id (copy the actual IDs from input_index.json), capability_availability (including knowledge_present_in_initial_context), adoption (each entry with unit/module/function, provenance_category: library_read/import_only/actual_invocation/explicitly_cited_reimplementation/semantic_similarity_origin_unknown/unknown, phases read/written/executed/verified/retained/unknown, actual_call_evidence, modified_or_inlined, observed_outcome, attribution_uncertainty), nonuse, methods_actually_executed, student_verification, failures_and_recovery, side_effects, spatial_and_orientation_analysis, appearance_and_resource_analysis, geometry_analysis, semantic_correspondence (gt_instance_ids, gt_semantic_label, student_object_names, confidence, basis, ambiguity, orientation_identifiability), evaluator_only_evidence, unsupported_or_unknown_claims, limitations, and human_rating=null. Cite evidence for every substantive statement. Finish after saving.
'''

COMPARISON_PROMPT='''You are an automated posthoc knowledge-comparison researcher. Read /app/input_index.json. All libraries and completed student outputs are frozen. You may inspect read-only public libraries, their actual research/validation evidence, pre-test audit, all anonymous visual reviews, all technical/adoption annotations, deterministic evaluation records, and original execution evidence through the indexed bundles. This is analysis only; do not modify knowledge or student results.

Compare the five libraries by substantive technical methods, applicability, verification, failure boundaries, and actual knowledge origins. Separate prior knowledge concretized by implementation from development-GT-derived implementation facts, ordinary strategy-trajectory evidence, active-exploration execution experience, and new validation discoveries. Source labels alone do not prove origin, novelty or causal necessity. Return canonical_semantic_vocabulary and, for each condition, canonical_semantic_methods: {canonical_label, definition, status: implemented/validated/unknown, module_functions_and_lines, actual_validation_evidence, origin_evidence, uncertainty}. Unify genuine synonyms across all libraries using the same canonical label; keep materially different techniques separate. Unknown is not absence. These actual semantic labels support ten pairwise library Jaccard comparisons, not code-text similarity. Retain links to the pre-test auditor's labels and explain any evidence-supported relabeling. Identify overlap and redundancy with evidence-supported semantic method comparisons rather than code-text similarity, number of functions or library length.

For the completed paired tasks, assess actual use/nonuse, execution versus mere mention/import, observable outcomes and side effects. All library conditions had the full SKILL text in their initial prompt; knowledge presence is different from library Read, import, an actual reached function call, explicitly cited hand reimplementation, or semantic similarity with unknown origin. Do not label the latter as proven learned-library adoption. Retain all 24 planned task/group outcomes, including missing deliverables. Show the planned denominator and observed delivery failures separately from quality among real renders; never silently complete-case-exclude a run or assign a fabricated zero visual score. Compare A1 vs A0, A3 vs A2, A4 vs A1, A5 vs A3 and A5 vs A4. Preserve mixed and negative results. Distinguish independent visual judgments, measured technical facts, semantic correspondence uncertainty and interpretation. A better scalar image score does not prove improved 3D structure. Never treat evaluator-generated checks as a student capability. Input amounts, hint/library lengths and actual model costs may differ; note confounds. One capability-acquisition round on a few tasks does not establish persistent recursive improvement, statistical significance, or long-term capability growth. Automated judges share the fixed base model and can have correlated errors. Human ratings are unavailable.

There is exactly one generated library per knowledge source and one student sample per task/group (four test tasks by six groups). Knowledge-generation variance and within-task student-sampling variance cannot be estimated. Four matched tasks do not establish statistical significance. The design has no content-matched text-only versus executable-tool ablation: report observed calls and verification, but do not causally claim tools outperform text. The common prespecified learning prompt already required assembly/hinge consistency, interpreting near-zero gap separately from proven contact, and inspecting output-connected material nodes. These are shared interpretation boundaries, not unique discoveries of a trajectory source; source-specific contributions need additional actual evidence.

Start with /reviews/compact_comparison_evidence.json, the actual observed tables and the pre-test library audit, then inspect only the specific original library/source evidence needed to support a claim. The compact evidence contains mechanically selected original annotation fields and source citations without controller-authored judgments. You are not responsible for per-mapping projection eligibility; that independent bounded review has its own actual SDK outputs. Do not repeat its 205-item workload or infer future mask scores. Preserve unknown information instead of reading every large raw index or state.

Write /app/knowledge_comparison.json as English JSON with annotation_kind=automated_model, canonical_semantic_vocabulary, libraries (condition, canonical_semantic_methods, substantive_methods, origins, validations, limits), pairwise_method_overlap_and_differences, prescribed_contrasts (each with paired_task_evidence, actual_adoption, spatial_outcomes, appearance_outcomes, geometry_outcomes, side_effects, uncertainty), complementary_knowledge_cases, redundancy_cases, prior_knowledge_vs_observed_experience, unsupported_transfer_claims, interpretation_limits, evidence_index, and human_rating=null. Use exact paths and recorded events. Unknown evidence remains unknown. Finish after saving the file.
'''
PROJECTION_PROMPT='''You are an independent automated projection-identity reviewer for ONE test scene and its six completed task/group runs. This is posthoc evaluation only. Read /app/input_index.json and the readable /projection_evidence/proposed_projection_mappings.json. The exact line-indexed JSONL copy is also preserved. Each line preserves one actual original technical proposal with its exact run_id, scene_id, zero-based mapping_index and original annotation_source. The index lists the six planned runs, original annotation paths and actual mapping counts. Review only these six runs. No student, frozen library, original annotation or proposal may be modified.

Separate entity identity/assembly membership/duplicate-instance uncertainty from ordinary limitations. A definite identity or membership conflict means measurement_eligible=false; insufficient evidence means null. Texture/shape differences, occlusion, hidden surfaces, orientation identifiability and masks not yet being measured do not by themselves rule out a supported 2D entity comparison; preserve them as non_identity_limits. High confidence alone cannot override contradictory identity evidence. Read exact names/parents/children from compact object_inventory.jsonl and actual GT instance statistics when needed, rather than repeatedly reading large full states. The original technical index is at /technical_evidence/<run>/index.json; its /evidence/ paths must be read with /technical_evidence/<run>/ substituted. All mounted technical evidence belongs to this scene only. Actual reference/final images, when delivered, are indexed locally.

Preserve original GT IDs, student object names, confidence, array order and mapping indices. Do not invent or repair mappings. Do not use future measured projection-mask scores. Every original proposal needs one reviewed entry at its provided mapping_index. For a genuine no-scene/no-proposal run use mappings:[]; a missing annotation remains unknown. Eligibility=true does not upgrade original confidence or bypass later deterministic exact-name/GT-ID checks. These judgments are model-proposed and not human-verified.

Write /app/projection_identity_review.json with annotation_kind=automated_model, scene_id, projection_correspondence_review:[{run_id,mappings:[{mapping_index,measurement_eligible:true/false/null,identity_ambiguity:[],non_identity_limits:[],basis:[],reason:string}]}], limitations and human_rating:null. Save a valid JSON incrementally after each completed run, retaining earlier reviewed entries. Never fill unfinished reviews with invented decisions. Complete all six runs within this bounded session; write concise evidence-based decisions rather than a general research essay. Finish after the file is saved.
'''
FOLLOWUP_PROMPT=PROJECTION_PROMPT.replace('ONE test scene and its six completed task/group runs',
    'ONE completed task/group run and ONLY its originally unreviewed mapping indices').replace(
    'the six planned runs','the one planned run').replace('Review only these six runs','Review only this run and the listed missing indices').replace(
    'Every original proposal needs one reviewed entry','Every listed missing original proposal needs one reviewed entry').replace(
    'Complete all six runs within this bounded session','Complete only the listed missing indices within this 240-second, 16-request session')+'''

This is the single prespecified missing-coverage followup round. Selection used only absent original mapping indices after all original scene sessions ended, never their eligibility values. /app/input_index.json lists expected_mapping_indices. Emit ONLY those original indices, do not renumber them and do not re-review indices already written by an earlier reviewer. Your input proposal subset preserves original fields and array positions. Write the same output schema with one actual run_id; use null when evidence is insufficient. Save actual decisions incrementally; do not claim a complete run just because this SDK session can end. There will be no automatic second followup or favorable-result resampling.
'''
REPORT_PROMPT='''You are a research reporter operating through the same fixed Claude Agent SDK and model backend as the experiment. All students, independent evaluations, semantic projection comparisons and earlier research reviews have ended. This is reporting only: do not change students, capability libraries, mappings, frozen predictions or measurements. Read /app/input_index.json and select evidence files from the read-only indexed bundles. Do not paste all raw trajectories into a single argument or invent results missing from the index.

Write the final report in Chinese to /app/REPORT_ZH.md. For user-facing file citations, use the original source paths in provenance.json, preferably relative to this experiment; guest-only /report_evidence, /evidence and /technical_evidence paths are reading locations and do not resolve outside the reviewer namespace. Code, function names, IDs and evidence paths may retain their actual spelling. Lead with what actually completed, the observed paired results and their limits. Separate deterministic observations, automated visual judgments, automated technical/source interpretations and hypotheses. Human ratings are unavailable and must remain null; never describe model judges as human evaluators. Cite exact files, actual images, code lines, tool events and recorded measurements. Read analysis/paired_projection_differences.json: compare only two-sided measured masks for the same scene and exact GT-instance-ID set. Do not interpret means over different covered entity sets as a group quality difference. Model-proposed semantic correspondences are not human-verified. Unknown correspondence, unmatched instances, symmetry, hidden geometry and unaligned coordinate frames do not justify fabricated 3D error.

Answer all ten questions explicitly with actual evidence: (1) What technical knowledge was actually found by direct development-GT inspection? (2) What substantive differences exist among A1-A5 libraries? (3) What knowledge redundancy exists, including all ten canonical-semantic-method Jaccard pairs and their evidence/unknown coverage? (4) Did students actually use the new tools or methods? (5) Did relative positions, orientations and spatial relationships improve? (6) Did materials, texture mapping and appearance improve? (7) Did active-exploration trajectories transfer better than ordinary strategy guidance? (8) What additional value, if any, did GT provide? (9) Are GT and exploration complementary? (10) What regressions or side effects occurred?

Use the predefined contrasts A1-A0, A3-A2, A4-A1, A5-A3 and A5-A4 with task-level matched evidence, retaining negative, mixed and unknown outcomes. Numeric defaults and parameterized synthetic examples alone are not leaked answers. A library in context, Read, import, an actual reached call, an explicitly cited manual reimplementation, and semantic similarity of unknown origin are distinct adoption evidence. Do not credit teacher instructions or evaluator-generated checks as student actions. Include concrete spatial/appearance examples and acknowledge when objective measurements do not establish visual improvement or 3D consistency. Materials with more nodes are not automatically better. Never collapse all dimensions into a single unvalidated score.

Describe the data split, GT permissions, common budgets, fixed model/effort, SDK ownership of tools, frozen optional public libraries, exact sources, technical completion/reproduction, actual engineering fixes and affected attempts, and remaining information-access limits. Summarize actual calls, reported input/output tokens, cached/reasoning subsets, wall time and observed CPU/memory resources; missing returned usage is unknown, Codex dollar billing is unknown, and Ofox calls are zero only if the recorded usage confirms that. Reporter cost is not yet available during its own generation and will be included in the final separate observed-usage file afterward; state that boundary.

This is one capability-acquisition and independent transfer round with an external knowledge/tool library. It does not show weight changes, model internalization, long-term retention, statistically significant gains, continuing recursive improvement or completed RSI. The small number of tasks, unmatched knowledge-input sizes, stochastic trajectories, same-model teacher/student/judges, automatic semantic correspondence and absent human labels limit interpretation. Retain every planned task/group in the denominator, including missing deliverables. Report delivery failures separately from conditional visual quality among actual renders; do not silently exclude failures or impute visual score zero. Do not assume the GT+exploration group is best.

There is exactly one generated library per knowledge source and one student sample per task/group (four test tasks by six groups). Knowledge-generation variance and within-task student-sampling variance cannot be estimated. Four matched tasks do not establish statistical significance. The design has no content-matched text-only versus executable-tool ablation: report observed calls and verification, but do not causally claim tools outperform text. The common prespecified learning prompt already required assembly/hinge consistency, interpreting near-zero gap separately from proven contact, and inspecting output-connected material nodes. These are shared interpretation boundaries, not unique discoveries of a trajectory source; source-specific contributions need additional actual evidence.

Finish after writing the report.
''' 

PROMPTS={'library-audit':LIBRARY_PROMPT,'visual':VISUAL_PROMPT,'technical':TECHNICAL_PROMPT,
         'knowledge-comparison':COMPARISON_PROMPT,'projection-review':PROJECTION_PROMPT,'projection-followup':FOLLOWUP_PROMPT,'report':REPORT_PROMPT}


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
    write(path,{'role':'visual_evaluator' if visual else ('research_reporter' if stage=='report' else ('projection_identity_reviewer' if stage in ('projection-review','projection-followup') else 'posthoc_annotator')),
                'tools':['Read','Write'] if visual or stage=='report' else TOOLS,
                'initial_images':[{'path':'/app/reference.png','label':'Reference image'},
                                  {'path':'/app/final.png','label':'Candidate reconstruction'}] if stage in ('visual','technical') else [],
                'readonly_mounts':mounts or [],'hint_enabled':False,'persistent_capability_enabled':False,
                'online_teacher_enabled':False})
    if stage in ('knowledge-comparison','report'):
        config=json.loads(path.read_text());config['auto_compact_window']=60000;write(path,config)
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
                for image in sorted((capture/'artifacts').rglob('*.png')):
                    copied(image,target/phase/'executions'/capture.name/'artifacts'/image.relative_to(capture/'artifacts'),provenance)
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
        delivery={name:(workspace/name).is_file() for name in ('build.py','scene.blend','final.png')}
        summarize(run)
        task=run.name.rsplit('-',1)[0];condition=run.name.rsplit('-',1)[1];scene=scenes[task]
        bundle=EXP/'acquisition_review_inputs/technical_evidence'/run.name;provenance=[]
        for name in ('sdk_events.json','evidence_index.json'):copied(run/'analysis'/name,bundle/name,provenance)
        copied(run/'inputs/prompt.txt',bundle/'student_initial_prompt.txt',provenance)
        request_rows=rows(run/'bridge/model_requests.jsonl')
        if request_rows:
            request_id=request_rows[0]['request_id']
            copied(run/'bridge'/request_id/'model_input.json',bundle/'initial_model_input.json',provenance)
            copied(run/'bridge'/request_id/'image_attachments.json',bundle/'initial_model_image_associations.json',provenance)
        text_tree(workspace,bundle/'final_source',provenance)
        for capture in sorted((run/'capture').glob('blender_*')):
            text_tree(capture,bundle/'executions'/capture.name,provenance)
            for image in sorted((capture/'artifacts').rglob('*.png')):
                copied(image,bundle/'executions'/capture.name/'artifacts'/image.relative_to(capture/'artifacts'),provenance)
        text_tree(run/'analysis/technical',bundle/'independent_evaluation',provenance)
        for name in ('GT.json','objects_in_view.json','metadata.json','instance_segmentation.png'):
            copied(Path(scene['directory'])/name,bundle/'reference_gt'/name,provenance)
        gt_derived=EXP/'data_preparation/new_scene_validation'/task
        for name in ('reference_instance_statistics.json','full_state.json'):
            copied(gt_derived/name,bundle/'reference_gt'/name,provenance)
        common_student=run/'analysis/technical/common_light'
        common_gt=gt_derived/'common_light'
        copied(common_student/'capture/common_light.png',bundle/'independent_evaluation/common_light/capture/common_light.png',provenance)
        for name in ('result.json','capture/common_light.png','capture/common_light_settings.json'):
            copied(common_gt/name,bundle/'reference_gt/common_light'/name,provenance)
        if condition!='A0':text_tree(EXP/'libraries'/condition,bundle/'available_library',provenance)
        index={'run':run.name,'scene_id':task,'condition':condition,'student_events':'/evidence/sdk_events.json',
               'student_evidence_index':'/evidence/evidence_index.json','student_initial_context':'/evidence/student_initial_prompt.txt',
               'delivery_status':{'artifacts':delivery,'missing_artifacts':[name for name,available in delivery.items() if not available],
                                  'outcome':'complete_deliverables' if all(delivery.values()) else 'missing_deliverables'},
               'actual_initial_model_request':'/evidence/initial_model_input.json','delivered_source':'/evidence/final_source',
               'actual_student_executions':'/evidence/executions','independent_evaluation':'/evidence/independent_evaluation',
               'original_object_inventory':'/evidence/independent_evaluation/original_inspection/capture/original/object_inventory.jsonl',
               'regenerated_object_inventory':'/evidence/independent_evaluation/source_only/capture/regenerated/object_inventory.jsonl',
               'gt_visible_instances':'/evidence/reference_gt/reference_instance_statistics.json',
               'common_light_comparison':{
                   'student_image':'/evidence/independent_evaluation/common_light/capture/common_light.png' if (common_student/'capture/common_light.png').exists() else None,
                   'gt_image':'/evidence/reference_gt/common_light/capture/common_light.png' if (common_gt/'capture/common_light.png').exists() else None,
                   'student_settings':'/evidence/independent_evaluation/common_light/capture/common_light_settings.json' if (common_student/'capture/common_light_settings.json').exists() else None,
                   'gt_settings':'/evidence/reference_gt/common_light/capture/common_light_settings.json' if (common_gt/'capture/common_light_settings.json').exists() else None,
                   'interpretation':'Independent evaluator products; common white world reduces original-light differences but retains geometry/material/camera and emission confounds. Missing scene means no image.'},
               'reference_gt':'/evidence/reference_gt','library':'none' if condition=='A0' else '/evidence/available_library',
               'interpretation':'Independent evaluation records are not student actions; GT/student world coordinates are not automatically aligned.',
               'provenance':'/evidence/provenance.json'}
        write(bundle/'index.json',index);write(bundle/'provenance.json',provenance)
        seed=EXP/'acquisition_review_inputs/technical'/run.name;seed.mkdir(parents=True,exist_ok=True)
        for name in ('reference.png','final.png'):
            if (workspace/name).exists():shutil.copy2(workspace/name,seed/name)
        write(seed/'input_index.json',index)
        config=EXP/'configs'/('acquisition_review_technical_'+run.name+'.json')
        common=session_file('technical',[{'source':str(bundle),'target':'/evidence'}])
        session=json.loads(common.read_text())
        if not delivery['final.png']:
            session['initial_images']=[{'path':'/app/reference.png','label':'Reference image'}]
        write(config,session)
        jobs.append({'id':run.name,'checkpoint':str(seed),'image':str(seed/'reference.png'),
                     'prompt':str(prompt_file('technical')),'session':str(config)})
    return jobs


def projection_review_jobs():
    require_students_ended();scenes={};jobs=[]
    for job in test_jobs():scenes.setdefault(job['id'].rsplit('-',1)[0],[]).append(job['id'])
    for scene,run_ids in sorted(scenes.items()):
        bundle=EXP/'acquisition_review_inputs/projection_review_evidence'/scene
        seed=EXP/'acquisition_review_inputs/projection_review'/scene
        provenance=[];proposals=[];run_records=[];mounts=[]
        for run_id in run_ids:
            source=EXP/'acquisition_reviews/technical'/run_id/'workspace/technical_annotation.json'
            status_path=source.parents[1]/'status.json'
            if status_path.exists():
                status=json.loads(status_path.read_text())
                assert status.get('finished_at') and status.get('owned_processes_stopped'),'Technical annotation must end before identity review.'
            mappings=[]
            if source.exists():
                copied(source,bundle/'runs'/run_id/'technical_annotation.json',provenance)
                mappings=json.loads(source.read_text()).get('semantic_correspondence',[])
                for position,proposal in enumerate(mappings):
                    proposals.append({**proposal,'run_id':run_id,'scene_id':scene,
                                      'mapping_index':position,'annotation_source':str(source)})
            images={}
            for name in ('reference.png','final.png'):
                image=EXP/'runs'/run_id/'workspace'/name
                copied(image,bundle/'runs'/run_id/name,provenance)
                images[name]='/projection_evidence/runs/'+run_id+'/'+name if image.exists() else None
            run_records.append({'run_id':run_id,'scene_id':scene,'annotation_available':source.exists(),
                                'annotation':'/projection_evidence/runs/'+run_id+'/technical_annotation.json' if source.exists() else None,
                                'mapping_count':len(mappings) if source.exists() else None,
                                'source_scene_exists':(EXP/'runs'/run_id/'workspace/scene.blend').exists(),
                                'images':images,'technical_index':'/technical_evidence/'+run_id+'/index.json'})
            mounts.append({'source':str(EXP/'acquisition_review_inputs/technical_evidence'/run_id),
                           'target':'/technical_evidence/'+run_id})
        bundle.mkdir(parents=True,exist_ok=True)
        (bundle/'proposed_projection_mappings.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in proposals))
        write(bundle/'proposed_projection_mappings.json',proposals)
        write(bundle/'provenance.json',provenance)
        index={'scene_id':scene,'planned_run_count':len(run_ids),'runs':run_records,
               'expected_mapping_count':len(proposals),'proposals':'/projection_evidence/proposed_projection_mappings.json',
               'original_indexed_proposals':'/projection_evidence/proposed_projection_mappings.jsonl',
               'technical_prefix_note':'Replace /evidence/ in each technical index with /technical_evidence/<run>/.',
               'scope':'Only this scene; no measured projection scores, knowledge generation or student feedback.'}
        write(seed/'input_index.json',index)
        mounts.insert(0,{'source':str(bundle),'target':'/projection_evidence'})
        config=EXP/'configs'/('acquisition_review_projection_'+scene+'.json')
        common=session_file('projection-review',mounts);shutil.copy2(common,config)
        reference=EXP/'runs'/run_ids[0]/'workspace/reference.png'
        jobs.append({'id':scene,'checkpoint':str(seed),'image':str(reference),
                     'prompt':str(prompt_file('projection-review')),'session':str(config)})
    return jobs


def merge_projection_reviews():
    expected={};scenes=set();original_sources={}
    for job in test_jobs():
        run_id=job['id'];scenes.add(run_id.rsplit('-',1)[0])
        source=EXP/'acquisition_reviews/technical'/run_id/'workspace/technical_annotation.json'
        expected[run_id]=list(range(len(json.loads(source.read_text()).get('semantic_correspondence',[])))) if source.exists() else None
        original_sources[run_id]=str(source)
    fragments=[];sources=[];missing_outputs=[]
    candidates=[('projection-review',scene,EXP/'acquisition_reviews/projection-review'/scene/'workspace/projection_identity_review.json') for scene in sorted(scenes)]
    candidates += [('projection-followup',job['id'],EXP/'acquisition_reviews/projection-followup'/job['id']/'workspace/projection_identity_review.json') for job in test_jobs()]
    for stage,identity,source in candidates:
        if source.exists():
            annotation=json.loads(source.read_text())
            for record in annotation.get('projection_correspondence_review',[]):
                fragments.append({'record':record,'source':str(source),'stage':stage})
            sources.append({'stage':stage,'identity':identity,'source':str(source)})
        elif stage=='projection-review':missing_outputs.append(str(source))
    grouped={}
    for fragment in fragments:grouped.setdefault(fragment['record']['run_id'],[]).append(fragment)
    merged=[];coverage=[]
    for run_id,indices in expected.items():
        records=grouped.get(run_id,[])
        mappings=[{**row,'decision_source':record['source'],'decision_stage':record['stage']}
                  for record in records for row in record['record'].get('mappings',[])]
        no_proposals=(indices==[])
        if records or no_proposals:
            merged.append({'run_id':run_id,'mappings':mappings,
                           'source_fragments':records,
                           'record_status':'no_proposals' if no_proposals else 'actual_model_fragments',
                           'original_annotation':original_sources[run_id]})
        received=[row['mapping_index'] for row in mappings]
        valid=[index for index in received if type(index) is int]
        missing=[index for index in (indices or []) if index not in valid]
        duplicates=sorted({index for index in valid if valid.count(index)>1})
        unexpected=[index for index in valid if indices is None or index not in indices]
        invalid=[index for index in received if type(index) is not int]
        complete=(indices is not None and (bool(records) or no_proposals) and not missing and not duplicates and not unexpected and not invalid)
        coverage.append({'run_id':run_id,'expected_mapping_indices':indices,'received_mapping_indices':received,
                         'missing_mapping_indices':missing,'duplicate_mapping_indices':duplicates,
                         'unexpected_mapping_indices':unexpected,'invalid_mapping_indices':invalid,
                         'source_fragment_count':len(records),'record_status':'no_proposals' if no_proposals else 'reviewed_or_unknown',
                         'complete':complete})
    unexpected_runs=[run for run in grouped if run not in expected]
    for run_id in unexpected_runs:
        records=grouped[run_id]
        merged.append({'run_id':run_id,'mappings':[{**row,'decision_source':record['source'],'decision_stage':record['stage']} for record in records for row in record['record'].get('mappings',[])],
                       'source_fragments':records,'record_status':'unexpected_run'})
    unresolved=[{'run_id':row['run_id'],'mapping_index':index,'status':'unknown',
                 'reason':'No actual review decision was written; missing coverage is not an eligibility judgment.'}
                for row in coverage for index in row['missing_mapping_indices']]
    result={'annotation_kind':'automated_model','merge_kind':'Mechanical per-run merge of original scene reviews and at most one missing-index followup; duplicates retained, never selected by outcome.',
            'projection_correspondence_review':merged,'source_reviews':sources,'missing_scene_outputs':missing_outputs,
            'expected_run_count':len(expected),'reviewed_run_count':len([row for row in merged if row['run_id'] in expected]),
            'expected_mapping_count':sum(len(indices or []) for indices in expected.values()),
            'reviewed_mapping_count':sum(len(row.get('mappings',[])) for row in merged),
            'mapping_coverage':coverage,'remaining_unreviewed':unresolved,'unexpected_runs':unexpected_runs,
            'followup_plan':'configs/acquisition_review_projection_followup_plan.json',
            'complete':not unexpected_runs and all(row['complete'] for row in coverage),'human_rating':None}
    write(EXP/'analysis/projection_identity_review.json',result)
    return {key:result[key] for key in ('complete','expected_run_count','reviewed_run_count','expected_mapping_count','reviewed_mapping_count')}


def projection_followup_jobs():
    require_students_ended()
    scenes=sorted({job['id'].rsplit('-',1)[0] for job in test_jobs()})
    for scene in scenes:
        status=json.loads((EXP/'acquisition_reviews/projection-review'/scene/'status.json').read_text())
        assert status.get('finished_at') and status.get('owned_processes_stopped'),'All original scene review sessions must end before missing-index selection.'
    plan_path=EXP/'configs/acquisition_review_projection_followup_plan.json'
    if plan_path.exists():return json.loads(plan_path.read_text())['jobs']
    assert not list((EXP/'acquisition_reviews/projection-followup').glob('*/status.json')),'Only one frozen followup plan is allowed.'
    merge_projection_reviews()
    aggregate=json.loads((EXP/'analysis/projection_identity_review.json').read_text())
    jobs=[];selection=[]
    for row in aggregate['mapping_coverage']:
        indices=row['missing_mapping_indices'];run_id=row['run_id']
        if not indices:continue
        source=EXP/'acquisition_reviews/technical'/run_id/'workspace/technical_annotation.json'
        original=json.loads(source.read_text())['semantic_correspondence']
        scene=run_id.rsplit('-',1)[0]
        proposals=[{**original[index],'run_id':run_id,'scene_id':scene,'mapping_index':index,'annotation_source':str(source)} for index in indices]
        bundle=EXP/'acquisition_review_inputs/projection_followup_evidence'/run_id
        seed=EXP/'acquisition_review_inputs/projection_followup'/run_id
        provenance=[];copied(source,bundle/'technical_annotation.json',provenance)
        for name in ('reference.png','final.png'):copied(EXP/'runs'/run_id/'workspace'/name,bundle/name,provenance)
        (bundle/'proposed_projection_mappings.jsonl').write_text(''.join(json.dumps(item,ensure_ascii=False)+'\n' for item in proposals))
        write(bundle/'proposed_projection_mappings.json',proposals);write(bundle/'provenance.json',provenance)
        index={'scene_id':scene,'planned_run_count':1,'run_id':run_id,'expected_mapping_indices':indices,
               'expected_mapping_count':len(indices),'proposals':'/projection_evidence/proposed_projection_mappings.json',
               'original_indexed_proposals':'/projection_evidence/proposed_projection_mappings.jsonl',
               'original_annotation':'/projection_evidence/technical_annotation.json',
               'technical_index':'/technical_evidence/'+run_id+'/index.json',
               'selection_rule':'Only original absent mapping indices, regardless of eligibility values. One followup round; no repeated decisions.',
               'scope':'One run and original missing indices only; no future mask scores or other reviewer decisions.'}
        write(seed/'input_index.json',index)
        mounts=[{'source':str(bundle),'target':'/projection_evidence'},
                {'source':str(EXP/'acquisition_review_inputs/technical_evidence'/run_id),'target':'/technical_evidence/'+run_id}]
        common=session_file('projection-followup',mounts)
        config=EXP/'configs'/('acquisition_review_projection_followup_'+run_id+'.json');shutil.copy2(common,config)
        jobs.append({'id':run_id,'checkpoint':str(seed),'image':str(EXP/'runs'/run_id/'workspace/reference.png'),
                     'prompt':str(prompt_file('projection-followup')),'session':str(config)})
        selection.append({'run_id':run_id,'original_missing_mapping_indices':indices,'source_annotation':str(source)})
    write(plan_path,{'frozen_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'rounds':1,
          'selection_rule':'Missing original run/index coverage only; no eligibility-based selection or resampling.',
          'source_coverage':aggregate['mapping_coverage'],'selection':selection,'jobs':jobs,'seconds':240,'model_requests':16})
    return jobs


def comparison_jobs():
    require_students_ended()
    for stage in ('visual','technical'):
        for status_path in (EXP/'acquisition_reviews'/stage).glob('*/status.json'):
            status=json.loads(status_path.read_text())
            assert status.get('finished_at') and status.get('owned_processes_stopped'),'Earlier review sessions are still running.'
    libraries,index=library_bundle();reviews=EXP/'acquisition_review_inputs/comparison_reviews';provenance=[];results=[];proposals=[];compact=[]
    order={row['run']:row['anonymous_id'] for row in freeze_blind_order()}
    for job in test_jobs():
        run=job['id'];anonymous=order[run]
        delivery={name:(EXP/'runs'/run/'workspace'/name).is_file() for name in ('build.py','scene.blend','final.png')}
        record={'run':run,'anonymous_id':anonymous,'delivery_status':delivery,
                'missing_artifacts':[name for name,available in delivery.items() if not available]}
        for stage,name,output in [('visual',anonymous,'visual_evaluation.json'),('technical',run,'technical_annotation.json')]:
            source=EXP/'acquisition_reviews'/stage/name/'workspace'/output
            copied(source,reviews/run/output,provenance)
            record[stage]='/reviews/'+run+'/'+output if source.exists() else 'unavailable'
            if stage=='technical':
                record['technical_annotation_available']=source.exists()
                record['projection_mapping_count']=None
                if source.exists():
                    annotation=json.loads(source.read_text())
                    fields=('capability_availability','adoption','nonuse','spatial_and_orientation_analysis','appearance_and_resource_analysis','side_effects','failures_and_recovery','limitations')
                    compact.append({'run_id':run,'scene_id':run.rsplit('-',1)[0],'annotation_source':str(source),
                                    'delivery_status':delivery,'fields':{key:annotation[key] for key in fields if key in annotation},
                                    'unavailable_fields':[key for key in fields if key not in annotation]})
                    mappings=annotation.get('semantic_correspondence',[])
                    record['projection_mapping_count']=len(mappings)
                    for position,proposal in enumerate(mappings):
                        proposals.append({**proposal,'run_id':run,'scene_id':run.rsplit('-',1)[0],
                                          'mapping_index':position,'annotation_source':str(source)})
        copied(EXP/'runs'/run/'analysis/technical/result.json',reviews/run/'deterministic_result.json',provenance)
        results.append(record)
    copied(EXP/'acquisition_reviews/library-audit/AUDIT/workspace/library_audit.json',reviews/'library_audit.json',provenance)
    for name in ('observed_results.json','paired_observed_differences.json','library_path_mentions.json','student_initial_condition_audit.json','serialized_backend_context_audit.json','common_light_index.json'):
        copied(EXP/'analysis'/name,reviews/name,provenance)
    reviews.mkdir(parents=True,exist_ok=True)
    write(reviews/'compact_comparison_evidence.json',compact)
    (reviews/'proposed_projection_mappings.jsonl').write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in proposals))
    write(reviews/'provenance.json',provenance)
    seed=EXP/'acquisition_review_inputs/knowledge_comparison';seed.mkdir(parents=True,exist_ok=True)
    write(seed/'input_index.json',{'libraries':index,'library_prefix_note':'Library evidence uses /evidence as in the pre-test audit.',
          'planned_run_count':len(test_jobs()),'runs':results,'pre_test_audit':'/reviews/library_audit.json',
          'observed_results':'/reviews/observed_results.json','prespecified_arithmetic_contrasts':'/reviews/paired_observed_differences.json',
          'library_path_inventory':'/reviews/library_path_mentions.json','actual_context_audits':['/reviews/student_initial_condition_audit.json','/reviews/serialized_backend_context_audit.json'],
          'common_light_index':'/reviews/common_light_index.json',
          'compact_comparison_evidence':'/reviews/compact_comparison_evidence.json',
          'projection_identity_scope':'Separate bounded per-scene SDK sessions review original mapping eligibility; this session does not repeat that workload.',
          'actual_technical_evidence':'/technical_evidence/<run>/index.json',
          'technical_prefix_note':'Within each run index, replace /evidence/ with /technical_evidence/<run>/ when following its paths.'})
    mounts=[{'source':str(libraries),'target':'/evidence'},{'source':str(reviews),'target':'/reviews'},
            {'source':str(EXP/'acquisition_review_inputs/technical_evidence'),'target':'/technical_evidence'}]
    config=session_file('knowledge-comparison',mounts)
    reference=json.loads((EXP/'configs/data_split.json').read_text())['development'][0]['reference']
    return [{'id':'COMPARISON','checkpoint':str(seed),'image':reference,
             'prompt':str(prompt_file('knowledge-comparison')),'session':str(config)}]


def observed_research_usage():
    sessions=[];scopes={}
    phase_directories=[('learning',EXP/'learning'),('validation',EXP/'validation'),('student',EXP/'runs')]
    phase_directories += [(stage,EXP/'acquisition_reviews'/stage) for stage in OUTPUTS]
    candidates=[(scope,path) for scope,directory in phase_directories for path in sorted(directory.glob('*')) if (path/'status.json').exists()]
    candidates += [('preflight',status.parent) for status in sorted((EXP/'preflight').rglob('status.json')) if (status.parent/'bridge/model_requests.jsonl').exists()]
    for scope,path in candidates:
        summary=summarize(path);requests=rows(path/'bridge/model_requests.jsonl');usage=rows(path/'bridge/token_usage.jsonl')
        reported={record['request_id'] for record in usage}
        record={'scope':scope,'session':path.name,'source_directory':str(path),'status':summary['status'],
                'model_requests':len(requests),'known_tokens':summary['tokens'],
                'requests_without_usage':[row['request_id'] for row in requests if row['request_id'] not in reported],
                'actual_models':sorted({row['actual_model'] for row in requests}),
                'reasoning_efforts':sorted({row['reasoning_effort'] for row in requests}),
                'errors':summary['model_errors']}
        sessions.append(record)
        aggregate=scopes.setdefault(scope,{'sessions':0,'model_requests':0,'known_tokens':{},'requests_without_usage':0})
        aggregate['sessions']+=1;aggregate['model_requests']+=len(requests)
        aggregate['requests_without_usage']+=len(record['requests_without_usage'])
        for key,value in summary['tokens'].items():aggregate['known_tokens'][key]=aggregate['known_tokens'].get(key,0)+value
    result={'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scopes':scopes,'sessions':sessions,
            'actual_billing_usd':None,'ofox_requests':0,
            'limitations':['Missing returned usage is unknown; observed totals are lower bounds.','Cached input and reasoning output are subsets, not additional tokens.','This records local executor usage, not controller chat usage or provider compute.','Report generation usage is only available after that session ends.']}
    write(EXP/'analysis/acquisition_review_research_usage.json',result)
    return result


def report_jobs():
    require_students_ended()
    projection=json.loads((EXP/'analysis/projection_summary.json').read_text())
    assert projection['complete'] is True,'Projection evaluation must finish before the research report.'
    assert projection['expected_run_count']==len(test_jobs()),'Projection coverage must match the frozen test jobs.'
    assert all(record.get('completed') for record in projection['runs']),'Projection run records must be complete.'
    comparison=EXP/'acquisition_reviews/knowledge-comparison/COMPARISON'
    state=json.loads((comparison/'status.json').read_text())
    assert state.get('finished_at') and state.get('owned_processes_stopped'),'Knowledge comparison must finish first.'
    assert (comparison/'workspace/knowledge_comparison.json').exists(),'The comparison result is not available.'
    summarize_reviews();observed_research_usage()
    bundle=EXP/'acquisition_review_inputs/report_evidence';provenance=[]
    for name in ('PROTOCOL.md','REQUEST.md','ENGINEERING_LOG.md','runtime_versions.json','start.json'):
        copied(EXP/name,bundle/name,provenance)
    text_tree(EXP/'configs',bundle/'configs',provenance)
    text_tree(EXP/'analysis',bundle/'analysis',provenance)
    for path in sorted((EXP/'analysis').rglob('*.png')):
        copied(path,bundle/'analysis'/path.relative_to(EXP/'analysis'),provenance)
    for path in sorted((EXP/'infrastructure').glob('*source_origin.json')):
        copied(path,bundle/'source_origin'/path.name,provenance)
    for stage,output in OUTPUTS.items():
        if stage=='report':continue
        for run in sorted((EXP/'acquisition_reviews'/stage).glob('*')):
            copied(run/'workspace'/output,bundle/'reviews'/stage/run.name/output,provenance)
    for job in test_jobs():
        run=EXP/'runs'/job['id'];target=bundle/'runs'/run.name
        copied(run/'status.json',target/'status.json',provenance)
        copied(run/'analysis/evidence_index.json',target/'student_evidence_index.json',provenance)
        for name in ('result.json','image_comparison.json','method_facts.json'):
            copied(run/'analysis/technical'/name,target/'technical'/name,provenance)
        copied(run/'analysis/projection/result.json',target/'projection/result.json',provenance)
        for name in ('reference.png','final.png'):
            copied(run/'workspace'/name,target/name,provenance)
    write(bundle/'provenance.json',provenance)
    seed=EXP/'acquisition_review_inputs/report';seed.mkdir(parents=True,exist_ok=True)
    index={'report_evidence':'/report_evidence','files':[str(Path('/report_evidence')/Path(row['bundle_path']).relative_to(bundle)) for row in provenance],
           'usage_before_report':'/report_evidence/analysis/acquisition_review_research_usage.json',
           'phase_usage':'/report_evidence/analysis/acquisition_review_usage.json',
           'library_method_overlap':'/report_evidence/analysis/acquisition_review_library_overlap.json',
           'projection_summary':'/report_evidence/analysis/projection_summary.json',
           'actual_projection_images':'/projection_evidence/<run>/mapping_XXX/ contains actual GT/student masks, overlay and available image crops. Replace each original run/analysis/projection prefix with /projection_evidence/<run>/.',
           'paired_projection_differences':'/report_evidence/analysis/paired_projection_differences.json',
           'technical_summary':'/report_evidence/analysis/technical_summary.json',
           'library_evidence':'/evidence/index.json','actual_student_technical_evidence':'/technical_evidence/<run>/index.json',
           'technical_prefix_note':'Replace /evidence/ in a technical run index with /technical_evidence/<run>/ when following its paths.',
           'planned_run_count':len(test_jobs()),
           'delivery_outcomes':[{'run':job['id'],'artifacts':{name:(EXP/'runs'/job['id']/'workspace'/name).is_file() for name in ('build.py','scene.blend','final.png')}} for job in test_jobs()],
           'output':'/app/REPORT_ZH.md','provenance':'/report_evidence/provenance.json'}
    write(seed/'input_index.json',index)
    mounts=[{'source':str(bundle),'target':'/report_evidence'},
            {'source':str(EXP/'acquisition_review_inputs/library_evidence'),'target':'/evidence'},
            {'source':str(EXP/'acquisition_review_inputs/technical_evidence'),'target':'/technical_evidence'}]
    mounts += [{'source':str(EXP/'runs'/job['id']/'analysis/projection'),
                'target':'/projection_evidence/'+job['id']} for job in test_jobs()]
    config=session_file('report',mounts)
    reference=json.loads((EXP/'configs/data_split.json').read_text())['development'][0]['reference']
    return [{'id':'REPORT','checkpoint':str(seed),'image':reference,'prompt':str(prompt_file('report')),'session':str(config)}]


def publish_report():
    source=EXP/'acquisition_reviews/report/REPORT/workspace/REPORT_ZH.md'
    if source.exists():
        shutil.copy2(source,EXP/'REPORT_ZH.md')
        write(EXP/'infrastructure/acquisition_review_report_provenance.json',
              {'source':str(source),'destination':str(EXP/'REPORT_ZH.md'),'writer':'Actual research_reporter Claude Agent SDK session',
               'raw_session':str(source.parents[1]),'controller_action':'Copy model-authored output unchanged; no research conclusions authored by the controller.'})
    summarize_reviews();observed_research_usage()


def batch(jobs,stage,args):
    queue=list(jobs);active={};completed=[];started=time.time();stop=False
    deadline=json.loads((EXP/'start.json').read_text())['deadline_epoch']
    seconds,calls=BUDGETS[stage]
    if stage in ('library-audit','knowledge-comparison','report'):workers=1
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
    methods={};unknown={};basis={};validation_status={}
    for entry in entries:
        condition=entry['condition']
        if 'canonical_semantic_methods' in entry:
            labels=entry['canonical_semantic_methods']
            methods[condition]={row['canonical_label'] for row in labels if row.get('status') in ('implemented','validated')}
            unknown[condition]=[row['canonical_label'] for row in labels if row.get('status')=='unknown']
            basis[condition]='SDK canonical labels with explicit implemented/validated status'
            validation_status[condition]='Per-method statuses supplied by the original annotation'
        elif 'methods' in entry:
            methods[condition]=set(entry['methods']);unknown[condition]=[]
            basis[condition]='Exact declared method labels from the actual SDK comparison; no controller semantic classification'
            validation_status[condition]='unavailable: per-method implementation/validation status was not returned'
        else:
            methods[condition]=set();unknown[condition]=['method_set_unavailable']
            basis[condition]='unknown: neither actual method-list schema was returned'
            validation_status[condition]='unavailable'
    pairs=[]
    reported_pairs={tuple(row['pair'].split('-')):row for row in annotation.get('semantic_jaccard',{}).get('pairs',[])}
    for first,second in combinations(sorted(methods),2):
        intersection=methods[first]&methods[second];union=methods[first]|methods[second]
        value=len(intersection)/len(union) if union and 'method_set_unavailable' not in unknown[first]+unknown[second] else None
        reported=reported_pairs.get((first,second))
        pairs.append({'conditions':[first,second],'shared_labels':sorted(intersection),'union_labels':sorted(union),
                      'known_methods_jaccard':value,'method_set_basis':{first:basis[first],second:basis[second]},
                      'per_method_validation_status':{first:validation_status[first],second:validation_status[second]},
                      'model_reported_jaccard':reported.get('jaccard') if reported else None,
                      'mechanical_value_matches_model':abs(value-reported['jaccard'])<=1e-9 if reported and value is not None else None,
                      'unknown_labels':{first:unknown[first],second:unknown[second]}})
    result={'annotation_source':str(source),'pairs':pairs,'method_sets':{key:sorted(value) for key,value in methods.items()},
            'interpretation':'Mechanical exact-label Jaccard from the actual SDK method sets. Structured canonical rows retain their explicit status filter; declared methods without statuses are not called validated. Unknown coverage is not absence. No controller semantic relabeling, code-text similarity or significance claim.',
            'method_set_basis':basis,'per_method_validation_status':validation_status,
            'model_supplied_semantic_jaccard':annotation.get('semantic_jaccard'),
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
            request_rows=rows(run/'bridge/model_requests.jsonl')
            usage_path=run/'bridge/token_usage.jsonl'
            usage_rows=rows(usage_path)
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
            write(EXP/'configs/data_split.json',{'test':[{'id':'FIXTURE','directory':str(EXP/'gt_fixture')}],
                'development':[{'reference':str(EXP/'runs/FIXTURE-A0/workspace/reference.png')}]})
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
            (EXP/'runs/FIXTURE-A0/workspace/final.png').unlink()
            technical=technical_jobs()
            assert len(technical)==6
            failed=next(job for job in technical if job['id']=='FIXTURE-A0')
            failed_session=json.loads(Path(failed['session']).read_text())
            failed_index=json.loads((Path(failed['checkpoint'])/'input_index.json').read_text())
            assert failed_session['initial_images']==[{'path':'/app/reference.png','label':'Reference image'}]
            assert not (Path(failed['checkpoint'])/'final.png').exists()
            assert failed_index['delivery_status']['missing_artifacts']==['build.py','scene.blend','final.png']
            complete=next(job for job in technical if job['id']=='FIXTURE-A1')
            assert len(json.loads(Path(complete['session']).read_text())['initial_images'])==2
            original_proposals=[{'gt_instance_ids':[3],'gt_semantic_label':'fixture object','student_object_names':['ObjectA'],'confidence':'high','basis':['fixture only'],'ambiguity':['shape differs'],'orientation_identifiability':'unknown'},
                                {'gt_instance_ids':[4],'gt_semantic_label':'fixture object','student_object_names':['ObjectB'],'confidence':'unknown','basis':[],'ambiguity':['duplicate identity uncertain'],'orientation_identifiability':'unknown'}]
            for fixture_job in fixture_jobs:
                write(EXP/'acquisition_reviews/technical'/fixture_job['id']/'workspace/technical_annotation.json',
                      {'semantic_correspondence':[] if fixture_job['id']=='FIXTURE-A0' else original_proposals})
            comparison_jobs()
            indexed=rows(EXP/'acquisition_review_inputs/comparison_reviews/proposed_projection_mappings.jsonl')
            assert len(indexed)==10
            for record in indexed:
                original=original_proposals[record['mapping_index']]
                assert all(record[key]==value for key,value in original.items())
            projection_jobs=projection_review_jobs()
            assert len(projection_jobs)==1
            projection_config=json.loads(Path(projection_jobs[0]['session']).read_text())
            assert len(projection_config['readonly_mounts'])==7
            assert all('/FIXTURE' in mount['target'] or mount['target']=='/projection_evidence' for mount in projection_config['readonly_mounts'])
            fixture_review=[]
            for fixture_job in fixture_jobs:
                original=[] if fixture_job['id']=='FIXTURE-A0' else original_proposals
                fixture_review.append({'run_id':fixture_job['id'],'mappings':[{'mapping_index':index,'measurement_eligible':None,'identity_ambiguity':[],
                    'non_identity_limits':[],'basis':[],'reason':'Synthetic coverage fixture only, no model judgment.'} for index in range(len(original))]})
            target=EXP/'acquisition_reviews/projection-review/FIXTURE/workspace/projection_identity_review.json'
            write(target,{'projection_correspondence_review':fixture_review})
            merged=merge_projection_reviews()
            assert merged['complete'] and merged['reviewed_run_count']==6 and merged['reviewed_mapping_count']==10
            fixture_review[1]['mappings'].pop()
            write(target,{'projection_correspondence_review':fixture_review})
            assert merge_projection_reviews()['complete'] is False
            original_status=EXP/'acquisition_reviews/projection-review/FIXTURE/status.json'
            write(original_status,{'status':'running'})
            try:
                projection_followup_jobs()
                raise RuntimeError('Followup was not blocked while an original session was running.')
            except AssertionError:
                pass
            write(original_status,{'status':'completed','finished_at':1,'owned_processes_stopped':True})
            followup=projection_followup_jobs()
            assert len(followup)==1 and followup[0]['id']=='FIXTURE-A1'
            followup_index=json.loads((Path(followup[0]['checkpoint'])/'input_index.json').read_text())
            assert followup_index['expected_mapping_indices']==[1]
            subset=json.loads((EXP/'acquisition_review_inputs/projection_followup_evidence/FIXTURE-A1/proposed_projection_mappings.json').read_text())
            assert len(subset)==1 and subset[0]['mapping_index']==1
            assert all(subset[0][key]==value for key,value in original_proposals[1].items())
            followup_output=EXP/'acquisition_reviews/projection-followup/FIXTURE-A1/workspace/projection_identity_review.json'
            write(followup_output,{'projection_correspondence_review':[{'run_id':'FIXTURE-A1','mappings':[{'mapping_index':1,'measurement_eligible':None,'identity_ambiguity':[],
                'non_identity_limits':[],'basis':[],'reason':'Synthetic merge fixture only.'}]}]})
            assert merge_projection_reviews()['complete'] is True
            merged_actual=json.loads((EXP/'analysis/projection_identity_review.json').read_text())
            actual_run=next(row for row in merged_actual['projection_correspondence_review'] if row['run_id']=='FIXTURE-A1')
            assert len(actual_run['mappings'])==2 and len({row['decision_source'] for row in actual_run['mappings']})==2
            assert projection_followup_jobs()==followup
            duplicate=json.loads(followup_output.read_text())
            duplicate['projection_correspondence_review'][0]['mappings'].append({'mapping_index':0,'measurement_eligible':True})
            write(followup_output,duplicate)
            assert merge_projection_reviews()['complete'] is False
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
            'two_ordered_valid_png_attachments':True,'missing_final_technical_run_retained_with_reference_only':True,'original_projection_proposal_fields_and_indices_preserved':True,'per_scene_projection_context_and_exact_merge_coverage_checked':True,'single_missing_index_followup_gate_plan_and_provenance_checked':True,'generic_fidelity_prompt_without_target_defects':True,
            'no_condition_library_or_gt_inputs_for_visual':True,'posthoc_stages_require_all_student_supervisors_finished':True,
            'shared_sdk_and_bridge_modified':False}
    write(EXP/'infrastructure/acquisition_review_offline_check.json',report)
    print(json.dumps(report),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['freeze','library-audit','visual','technical','knowledge-comparison','projection-review','projection-followup','merge-projection-review','report','summarize','check'])
    parser.add_argument('--prepare-only',action='store_true')
    parser.add_argument('--workers',type=int,choices=[1,2,4],default=2)
    parser.add_argument('--base-port',type=int,default=19365)
    parser.add_argument('--run',action='append',help='Review selected IDs after the complete student phase has ended.')
    args=parser.parse_args()
    if args.stage=='freeze':freeze_blind_order()
    elif args.stage=='summarize':print(json.dumps(summarize_reviews()),flush=True)
    elif args.stage=='check':offline_check()
    elif args.stage=='merge-projection-review':print(json.dumps(merge_projection_reviews()),flush=True)
    else:
        jobs={'library-audit':library_audit_jobs,'visual':visual_jobs,'technical':technical_jobs,
              'knowledge-comparison':comparison_jobs,'projection-review':projection_review_jobs,'projection-followup':projection_followup_jobs,'report':report_jobs}[args.stage]()
        if args.run:jobs=[job for job in jobs if job['id'] in args.run]
        write(EXP/'configs'/('acquisition_review_'+args.stage+'_jobs.json'),jobs)
        if args.prepare_only:print(json.dumps({'stage':args.stage,'prepared':len(jobs),'model_calls':0}),flush=True)
        else:
            batch(jobs,args.stage,args)
            if args.stage in ('projection-review','projection-followup'):print(json.dumps(merge_projection_reviews()),flush=True)
            if args.stage=='report':publish_report()
