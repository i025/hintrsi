"""Blinded visual reviews and evidence-linked trajectory annotations via the same SDK."""
import argparse
import json
from pathlib import Path
import random
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'experiments/experiment_02_teacher_guided_exploration'
sys.path.insert(0,str(ROOT/'harness'))
sys.path.insert(0,str(ROOT/'analysis'))
from run_exploration import batch, student_jobs, write
from summarize_run import summarize

VISUAL_PROMPT='''You are an independent automated visual evaluator, not a human rater. You receive three real images: the reference, the current reconstruction (the candidate), and the initial reconstruction before additional execution. The labels explicitly identify them. Read the images themselves. No experimental group, teacher hint, preferred outcome, or other candidate is provided.

Describe this candidate independently. Do not assume it improved, or that every scene has the same defect. Compare visible object geometry, spatial layout and occlusion, materials/texture, viewpoint and lighting. Pay attention to visible chair support and connections in office scenes, the door leaf silhouette and foreground occlusion in bedroom scenes, and the right countertop texture in kitchen scenes. RGB alone cannot establish true mesh contact, collision, hidden geometry, or long-term learned capability. Do not turn invisible differences into errors.

Write /app/visual_evaluation.json as English JSON with keys: annotation_kind (automated_model), scene_description, initial_target_observations, candidate_target_observations, target_resolution (resolved/partial/unresolved/unknown), target_change (improved/unchanged/worse/unknown), overall_visual_change (improved/unchanged/worse/mixed/unknown), geometric_plausibility_observations, new_visible_defects, other_changes, evidence (an array of descriptions with image label and normalized image region [left,top,right,bottom]), uncertainty, and human_rating (null). Explain partial or unknown judgments. Do not produce an aggregate numeric score. Finish after writing the file.
'''

TECHNICAL_PROMPT='''You are an automated evidence annotator analyzing a completed Blender checkpoint branch. This is posthoc analysis, not a teacher interaction. Never change reconstruction files. Inspect /app/evidence/index.json, sdk_events.json, baseline_build.py, the delivered source under final_source/, the actual executed code captures under executions/, saved scene states under scene_states/, and target_geometry.json when available. The teacher diagnosis and exact received guidance are in evidence/teacher_diagnosis.json and received_guidance.txt; distinguish prior suggestions from techniques actually adopted. The reference and final render are real image inputs; initial.png is also available. No GT hidden geometry is provided.

The scene_states/ files and target_geometry.json are independent evaluator outputs, not student actions. They may establish final geometry/material facts but do not show that the student measured contact, cast floor rays, extracted state, regenerated independently, or performed a controlled render. Credit a student check or technique only from its actual SDK events and executed source in executions/. Never attribute the controller's evaluation code or measurements to student discovery.

Files under evidence/temporary_artifacts/ are actual student-generated temporary files recovered after session end, with their original paths recorded in temporary_artifact_provenance.json. They are not evaluator renders; correlate them with the real SDK tool events before assigning an observation/check label.

Distinguish (a) visible proposals, (b) code written, (c) code actually executed, (d) observations/verification actually performed, and (e) methods retained in the final scene. Cite concrete bundle paths, SDK event indices/tool call IDs, code lines or object/node names. An execution exit alone is not proof every helper or branch ran; use source reachability and saved scene state. Do not invent hidden reasoning. A technique mentioned in a hint is not an executed strategy. Inherited code technique is different from a new action in this branch. Do not inherit the previous run's render-inspection/camera-revision behavior just because its final checkpoint is supplied.

Blender may return exit code zero after a Python traceback. Inspect execution stdout/stderr, actual saved artifacts and subsequent recovery; do not call an exception-producing candidate successful from its exit code alone.

Multiple candidate files alone show generation, not comparison. An actual_comparison claim needs student-visible renders or measurements plus observable comparison/selection evidence in the SDK trace. If the evidence is insufficient, mark unknown rather than infer hidden reasoning. Local image texture mapping on a real object is not automatically a 2D shortcut; separately flag a full-reference image plane only when actual code/scene evidence shows it replaces scene reconstruction.

Use these generic labels where actually supported: parameterized_helpers, primitive_mesh_assembly, bevel_edges, weighted_normals, constant_principled_materials, explicit_world_coordinates, relative_part_coordinates, loop_repetition, perspective_look_at_camera, area_lighting, cycles_denoising, geometry_surface_patterns. Additional semantic labels may describe actual material nodes/mapping, assembly alignment, wheel reorientation, support geometry, hinge/doorway changes, geometry checking, visibility tests, controlled comparisons and distinct verification methods. Reuse a common label for semantically equivalent techniques. Numeric parameter changes alone are not a new modeling technology. Unknown is not absence.

Use the preferred semantic names and definitions in /app/evidence/strategy_vocabulary.json. Add a new label only for an evidence-supported technique not covered there, with an explicit definition. Do not assign a listed label merely because it appears in the vocabulary or teacher hint.

Write /app/trajectory_annotation.json as English JSON with:
- observable_diagnosis: evidence of error discovery/measurement, or unknown, without claims about hidden knowledge.
- actions: an array of {label, description, phase: proposed/written/executed/verified/retained/unknown, evidence}.
- strategies: an array of {label, scope: generic/scene/target, status: executed/retained/unknown, inherited_from_checkpoint: boolean, evidence}. Only executed/retained labels will enter overlap metrics.
- candidates: an array of {hypothesis, code_paths, technique_difference: numeric_parameter/execution_order/modeling_technique/executable_check/verification_mechanism/unknown, actually_executed, actual_comparison, retained, evidence, observed_result, side_effects, knowledge_origin: teacher_prior/natural_checkpoint/branch_discovery/unverified_hypothesis/unknown, unvalidated_parts}. Include actual rejected/abandoned variants; do not invent candidates that were only requested.
- exploration_assessment: {distinct_executed_technical_paths, actual_comparison, new_validation_method, explanation, evidence}. Do not count trace length or repeated failure as valuable exploration.
- failure_or_stopping_observations: actual errors, lack of verification, unchanged outputs, or unknown.
- candidate_knowledge: an array of {problem, observed_defect, cause_hypothesis, executed_method, evidence, applicability, verification, side_effects, unvalidated, origin, reusable_snippet_path}. A full scene program is not a general skill; leave snippet null if none exists. Cross-scene transfer is untested.
- limitations.

Keep claims concise and grounded. Do not infer strategy success from a condition name or the teacher's expectations. Finish after saving the JSON.
'''


def freeze_blind_order():
    ids=[j['id'] for rep in (1,2) for j in student_jobs(rep)]
    random.Random(20261128).shuffle(ids)
    write(EXP/'configs/blind_order.json',[{'anonymous_id':'V'+str(i+1).zfill(3),'run':run}
                                         for i,run in enumerate(ids)])


def visual_jobs():
    jobs=[]
    for row in json.loads((EXP/'configs/blind_order.json').read_text()):
        run=EXP/'runs'/row['run']
        if not run.exists():continue
        seed=EXP/'review_inputs/visual'/row['anonymous_id']
        seed.mkdir(parents=True)
        for name in ('reference.png','final.png'):shutil.copyfile(run/'workspace'/name,seed/name)
        shutil.copyfile(EXP/'checkpoints'/run.name[:3]/'final.png',seed/'initial.png')
        prompt=EXP/'prompts/visual_review.txt'
        prompt.write_text(VISUAL_PROMPT)
        config=EXP/'configs/visual_review.json'
        write(config,{'role':'visual_evaluator','tools':['Read','Write'],'hint_enabled':False,
                     'additional_images':[{'path':'/app/initial.png','label':'Initial reconstruction before additional execution'}]})
        jobs.append({'id':row['anonymous_id'],'checkpoint':str(seed),'image':str(seed/'reference.png'),
                     'prompt':str(prompt),'session':str(config)})
    return jobs


def technical_jobs():
    cases={c['scene']:c for c in json.loads((EXP/'configs/cases.json').read_text())}
    jobs=[]
    for job in student_jobs(1)+student_jobs(2):
        run=EXP/'runs'/job['id']
        summarize(run)
        seed=EXP/'review_inputs/technical'/run.name
        evidence=seed/'evidence'
        evidence.mkdir(parents=True)
        for name in ('reference.png','final.png'):shutil.copyfile(run/'workspace'/name,seed/name)
        shutil.copyfile(EXP/'checkpoints'/run.name[:3]/'final.png',seed/'initial.png')
        shutil.copyfile(EXP/'checkpoints'/run.name[:3]/'build.py',evidence/'baseline_build.py')
        shutil.copyfile(run/'analysis/sdk_events.json',evidence/'sdk_events.json')
        shutil.copyfile(run/'analysis/evidence_index.json',evidence/'index.json')
        shutil.copyfile(EXP/'analysis/strategy_vocabulary.json',evidence/'strategy_vocabulary.json')
        shutil.copyfile(run/'capture/temporary_artifact_provenance.json',evidence/'temporary_artifact_provenance.json')
        if (run/'capture/temporary_artifacts').exists():
            shutil.copytree(run/'capture/temporary_artifacts',evidence/'temporary_artifacts')
        final=evidence/'final_source'
        final.mkdir()
        for path in (run/'workspace').rglob('*'):
            if path.is_file() and '.git' not in path.parts and path.suffix not in ('.blend','.blend1','.blend2'):
                target=final/path.relative_to(run/'workspace');target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,target)
        executions=evidence/'executions'
        for capture in sorted((run/'capture').glob('blender_*')):
            target=executions/capture.name;target.mkdir(parents=True)
            for name in ('command.json','result.json','python_expr.txt','stdout.log','stderr.log'):
                if (capture/name).exists():shutil.copyfile(capture/name,target/name)
            if (capture/'code').exists():shutil.copytree(capture/'code',target/'code')
            for image in (capture/'artifacts').rglob('*.png'):
                dest=target/'images'/image.relative_to(capture/'artifacts');dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(image,dest)
        states=run/'analysis/technical/capture'
        dest=evidence/'scene_states';dest.mkdir()
        for name in ('final_state.json','regenerated_state.json','state_open_results.json'):
            if (states/name).exists():shutil.copy2(states/name,dest/name)
        if (states/'states').exists():shutil.copytree(states/'states',dest/'checkpoints')
        geometry=states/'target_geometry/geometry.json'
        if geometry.exists():shutil.copy2(geometry,evidence/'target_geometry.json')
        diagnosis=EXP/'teachers'/run.name[:3]/'workspace/teacher_diagnosis.json'
        shutil.copyfile(diagnosis,evidence/'teacher_diagnosis.json')
        hints=json.loads((EXP/'hints'/(run.name[:3]+'.json')).read_text())['hints']
        (evidence/'received_guidance.txt').write_text(hints[run.name.split('-')[1]] or 'No additional guidance.')
        prompt=EXP/'prompts/technical_review.txt';prompt.write_text(TECHNICAL_PROMPT)
        config=EXP/'configs/technical_review.json';write(config,{'role':'trajectory_annotator','tools':['Read','Glob','Grep','Write'],'hint_enabled':False})
        jobs.append({'id':run.name,'checkpoint':str(seed),'image':str(seed/'reference.png'),
                     'prompt':str(prompt),'session':str(config)})
    return jobs


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=['freeze','visual','technical'])
    args=parser.parse_args()
    if args.stage=='freeze':freeze_blind_order()
    elif args.stage=='visual':batch(visual_jobs(),'visual_reviews',EXP/'visual_reviews',600,30)
    else:batch(technical_jobs(),'technical_reviews',EXP/'technical_reviews',900,50)
