import json
import sys
import time
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
SERVER=Path('/srv/lab-disks/disk2/users/xymo')
rows=json.loads((OUT/'results/attempt_metrics.json').read_text())
if any(r['status']!='complete' for r in rows) and time.time()<1795651320-1800:
    raise RuntimeError('Wait for core results or the final30-minute reporting window')
sys.path.insert(0,str(OUT/'source'))
from codex_cli_bridge import default_command

papers=[
('SceneEvolve','2610.37046','Executable 3D code and teacher-driven reusable harness evolution with fixed model/action/backend.'),
('Trace2Skill','2603.25158','Inductive consolidation of broad execution trajectories into reusable transferable skills.'),
('SKILL-KD','2607.28048','Contrast student failure and teacher trajectory, evaluate skill patches by student reruns and consolidate trace-linked edits.'),
('SkillGen','2605.10999','Contrast successes/failures and empirically evaluate skill interventions for both repairs and regressions.'),
('Socratic Skill Learning','2610.17860','Interleave educator guidance and student practice, then evaluate reuse in fresh sessions.'),
('Teaching the Harness','2611.13144','Student-aware diagnostic probes and matched-development admission of reusable skills.'),
('DoVer','2512.06749','Targeted interventions verify debugging hypotheses; multiple distinct repairs can resolve one failure.'),
('GEPA','2507.19457','Natural-language reflection over trajectories proposes/tests prompt updates and combines complementary lessons.'),
('SimWorld Studio','2605.09423','Verifier feedback supports evolving engine-level 3D environment coding tools/skills and curricula.')]
data={'result_root':str(OUT),'report_snapshot_unix':time.time(),
    'planned_window_UTC':'2026-11-25 18:02:00 to2026-11-26 00:02:00',
    'planned_window_beijing':'2026-11-26 02:02:00 to08:02:00','deadline_unix':1795651320,
    'core_attempts':rows,'actual_cli_base_command':default_command(),
    'papers':[{'name':n,'url':'https://arxiv.org/abs/'+i,'abstract_level_verified_scope':s} for n,i,s in papers],
    'important_scope_facts':{
        'historical_student_files':117,'historical_student_deep_files_total':10,'student_deep_events_total':913,
        'development_knowledge_cohort_deep_complete_sequences':8,'development_cohort_events':397,
        'postfreeze_audit_only_students':2,'postfreeze_audit_only_events':516,
        'postfreeze_audit_field_scope':'All245/271 event IDs supplied, long strings clipped to1800characters; no feedback to libraries/students.',
        'historical_teacher_files':104,'historical_teacher_deep_complete_files':4,'teacher_deep_events':49,
        'other_historical_preflight_trajectory_files':36,'Ofox_model':'deepseek/deepseek-v4.1-flash-1017',
        'Ofox_model_attempts':10,'Ofox_pass_fail_incomplete':[3,3,4],'Ofox_pre_model_infrastructure_launches':2,
        'batch12_new_segment_graded':53,'batch12_solved':1,'batch12_formally_unsolved':52,'batch12_interrupted':3,'batch12_not_started_tasks':3,
        'batch12_stop':'Unexpected native operation: mcp_tool_call, not an algorithmic failure for all53 attempts',
        'scene_text_unique_files_initial':136,'scene_text_unique_files_final':140,'scene_text_full_files_final':132,'scene_prefix_files':8,'scene_prefix_cap':100000,
        'scene_raw_trajectory_jsonl_reviewed':6,'scene_raw_trajectory_jsonl_all_prefix_only':True,
        'scene_stage_event_logs_full':25,'scene_incremental_patch_files':21,'scene_build_files':10,
        'scene_native_visual_audit_cases':3,'scene_render_images_reviewed':6,'scene_distinct_reference_photos':2,
        'scene_reference_T01_E02_same_historical_kitchen':True,'scene_bundle_index_only_files':27,
        'scene_geometry_addendum':'Two old .blend checkpoints loaded read-only by original Blender4.2.10,1thread/noGPU/no render;874Bpyobjects each,48mesh semantic subset,1128AABBpairs each, no exact collision/contact test.',
        'no_new_Scene_learning_or_reconstruction_trial':True,'no_weight_training':True,'no_V2_recursive_learning':True,
        'no_claim_of_first_or_statistical_significance':True,
        'no_source_ablation':'Cannot measure/rank marginal transfer value of individual source trajectories from this experiment.',
        'runtime_boundary':'Reused verified original VM/runtime/outer-container/firewall isolation; original SDK inner bwrap/socat availability limitation was not repaired or claimed solved.',
        'CLI_boundary':'SDK messages/tools serialized in JSON to fresh native CLI exec actions, not native API role/sampling equivalence. CLI defaults for temperature/top_p/max_tokens. Requested model and low effort fixed.'}}
for name in ['config/run_manifest.json','config/protocol.json','config/task_split.json','config/development_sources.json',
    'config/library_delivery.json','config/extraction_budget.json','config/knowledge_freeze.json',
    'config/optional_hint_plan.json','config/common_prompt_repair.json','config/evaluation_triage.json','audit/inventory_summary.json','audit/baseline_addendum_sources.json','audit/scene_inventory_summary.json','audit/scene_geometry_audit_sources.json',
    'audit/source_comparison.json','logs/engineering_fixes.json','results/model_condition_validation.json',
    'results/cost_breakdown_summary.json','results/resource_summary.json','evidence/scene_geometry/execution_records.json','results/actual_usage_summary.json']:
    p=OUT/name
    if p.exists():data[name]=json.loads(p.read_text())
data['frozen_libraries']={g:(OUT/'knowledge'/f'{g}_v1.md').read_text() for g in ['K0','K1','K2']}
data['generation_intermediates']={g:(OUT/'knowledge'/f'{g}_analysis_v1.md').read_text() for g in ['K0','K1','K2']}
data['knowledge_artifacts']=[{'path':str(p),'words':len(p.read_text().split()),'characters':len(p.read_text())}
    for p in sorted((OUT/'knowledge').rglob('*.md'))]
data['acquisition_scope_note']='The raw shared extraction packet used mechanical per-string/tool-input/patch caps and selected formal fields. Some formal failure assertion tails visible in later full audits were not in that extraction packet. Do not retroactively attribute later audit-only failure diagnoses or E01/E02 to learned libraries.'
data['authoritative_selection_audits']='posthoc_selection_matched_* and pooled_selection_matched.md correspond to current core rows. Earlier posthoc_selection_* and pooled_selection.md are superseded conditioning evidence; keep their real outcomes only in the extra-attempt discussion.'
data['english_audits']={}
for pattern in ['audit_D*.md','audit_E*.md','audit_S*.md','audit_teacher_chain_reduced.md','evaluation_diagnostic_*.md','posthoc_*.md','library_review.md','pooled_*.md']:
    for p in sorted((OUT/'audit').glob(pattern)):data['english_audits'][str(p)]=p.read_text()
for name in ['extra_attempt_metrics.csv','evaluation_diagnostics.csv','hint_attempt_metrics.csv','audit/historical_cli_usage.csv','commands_used.md']:
    p=OUT/name
    if p.exists():data[name]=p.read_text()
instruction='''Write the final Chinese presentation research report, about7000-12000 Chinese characters, solely from the supplied completed evidence. Use the user's required A-G structure plus a deliverable index. Start with the actual main Test outcome and its limits; do not assume positive hypotheses. This report may be drafted before the six-hour deadline, so distinguish result closure from the still-running monitor and leave final cleanup/accounting to the appended evidence.

A: audit coverage with exact reviewed/unreviewed scope; mandatory Claude I2/H1/B/H/M/I failure, IgelB3 and SQLfmt13 cases; Scene teacher recognition/diagnosis/update/adoption chain; copies are not independent attempts. Initial historical task descriptions were absent from first individual audit packets but supplied in the successful teacher-chain addendum. Never call all257files fully audited.
B: original source13/public commit, exactly which files changed and why, original SDK/Bridge/evaluator reused, actual Terra/low and ignored differing global default, real commands. Explain the actual data-field fix, production forwarding failure, preserved oldsuccessfulB0, pre-model abortedK0, uniform repaired Selection rerun, oversized audit failure, and the subsequently observed SDK identity-line difference between empty/nonempty append paths. The tiny SDK default repair gives B0 an empty reminder and leaves knowledge-path code unchanged. Previous capability_v1 Selection audits/grades remain superseded evidence, and all four Selection groups are revalidated as capability_v1_matched_prompt. Knowledge was frozen after the earlier Selection and before Test, never updated from the matched revalidation or Test feedback. Ongoing first Test K1/K2 used the unchanged nonempty path; compare actual requests for common system text (excluding the capability), tools and user issue before claiming matched conditions. No student solution was manually repaired. Original inner sandbox limits remain.
Also explain the real matched-Selection K2 evaluation anomaly: initial new-ctrf.json absent, scored0/80and80/116 without a complete test report. Save that original result; first diagnostic launcher found no archived top-level patch and did not evaluate, then one actual unchanged-patch/unchanged-env re-evaluation completed80/80and116/116. The only evaluator code change saves full stdout/stderr AFTER the container command has already finished, without changing scoring/tests/commands/environment. Use the first complete report, not the best of many trials; there was no student retry. Initial root cause remains unknown, do not assert Node/JIT as proven. K2 selection wall includes diagnosis/recovery and is not a skill-efficiency effect. Evaluation-only costs and the no-patch invocation are separate. Do not mistake the original missing report for80executed failing assertions or the recovery for code/knowledge improvement.
C: K0descriptions/ownprior only, K1chronological raw distillation, K2evidence-grounded inferredsubgoal/observedstate units and functional alignment before library generation. Same8rawsources/input budget/model/calls for K1/K2; include pre-metadata-fix extra generation cost, deterministic first4unit delivery and actual lengths644/578/526. No longer-K2 advantage, but unequal content/lengths remain a limitation. No extraGT or student tries for K2. Explain Selection decisions and noV2; allversions/rawoutputs retained. Test frozen before any Test run, no Test feedback used to update libraries.
D: Put exactly <<CORE_RESULTS_TABLE>> where the program will insert all12planned Selection/Test rows, and <<EXTRA_RESULTS_TABLE>> for all superseded/technical starts (currently six launch rows). Do not invent or manually reconstruct table numbers. Explain official full success versus F2Pauxiliary/P2P; missing/technical grades are not normal failures. Report actual tool/request/input/output/cache/time costs, cache is a subset. Aggregate Testsuccess has only2tasks pergroup, one attempt/cell, no significance. Keep Selection separate from Test. Put <<OPTIONAL_HINT_RESULTS>> for conditional Hint exploration results or skip reason. Optional Hint may still be running when this core report is drafted: do not hard-code its status/outcomes elsewhere, as the program will insert its final real results and analysis link later. No hint-transfer claims without independent transfer test. Use <<FINAL_ACCOUNTING>> for final totals/cleanup; do not give stale experiment-wide totals from before this report-writing call. SDK reported dollars are proxy estimates; actual settled CLI dollar cost unknown. This monitoring chat's own orchestration usage is outside the spawned-CLI ledger, so label the accounting scope.
E: use actual actions/events and actual input proof, not model self-claims, for adoption. Distinguish behavior consistent with a rule from causal adoption; Base can do similar checks. Discuss repairs/regressions/overhead/transfer failures only supported by traces; do not attribute normal stochastic failures to a skill without evidence. Assess whether K2 extracted something substantively absent in K1, not just a nicer table. No individual-source learning-value ranking is supported by this pooledcohort. No hidden-test diagnosis may be invented.
F: proposals for Scene transfer (programbehavior to3Dsemanticstate, behavioralconstraints togeometry/relations, tests togeometry/renderchecks, cross-task tocross-object/scene). Camera changes can validly change projectedsize without geometry resizing; do not confuse different implementations with errors. Include the actual SG01 read-only audit of two existing saved Blend checkpoints: material/panel bounds changed, stand/camera unchanged, and AABB lower bounds alone do not prove contact or quality. Initial Scene text audit136files plus4newfulltexts gives140textfiles(132full/8prefix), plus2oldbinarycheckpoint probes. No new Scene reconstruction/learning/quality-transfer trial or aesthetic teacher was implemented. Code outcomes are not evidence that the learned libraries improve Scene tasks.
G: cite all9provided primary paper URLs near the specific overlap. We actually opened abstract pages, not a full systematic literature review. Do not claim multi-trajectory summarization, teacher guidance, skill validation or frozen-model self-improvement are novel. At most report limited exploratory evidence for explicit state-aligned, implementation-independent knowledge under these conditions, as the actual results warrant.

Use absolute clickable file links under result_root for deliverables; preserve exact source paths/event IDs where useful. Do not expose internal web ref IDs. Do not claim missing experiments, retries, native tools or intermediate replay occurred. Do not propose student code edits or new experiments as if performed. Natural-language output is Chinese for this user-facing report only; English raw artifacts stay unchanged.

EVIDENCE DATA:\n'''
prompt=instruction+json.dumps(data,ensure_ascii=False,separators=(',',':'))
if len(prompt)>750000:raise RuntimeError('Final report packet too large; inspect scope explicitly')
(OUT/'config/final_report_prompt.txt').write_text(prompt)
print(json.dumps({'prompt':str(OUT/'config/final_report_prompt.txt'),'characters':len(prompt)}))
