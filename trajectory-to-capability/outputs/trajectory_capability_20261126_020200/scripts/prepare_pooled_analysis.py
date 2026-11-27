"""Prepare read-only cross-group evidence; never update a learner or library."""
import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq

p=argparse.ArgumentParser()
p.add_argument('--stage',choices=['selection','test'],required=True)
a=p.parse_args()
OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
rows=[r for r in json.loads((OUT/'results/attempt_metrics.json').read_text()) if r['stage']==a.stage]
if any(r['status']!='complete' for r in rows):raise RuntimeError('Wait for complete paired results')
descriptions={r['instance_id']:r['problem_statement'] for r in pq.read_table(
    '/srv/lab-disks/disk2/users/xymo/hint-baseline-run/data/deep_swe_tasks.parquet',
    columns=['instance_id','problem_statement']).to_pylist()}
data={'stage':a.stage,'public_task_descriptions':{t:descriptions[t] for t in {r['task'] for r in rows}},
    'attempts':rows,'libraries':{g:(OUT/'knowledge'/f'{g}_v1.md').read_text() for g in ['K0','K1','K2']},
    'individual_observational_audits':{},'official_evaluations':{},'final_student_patches':{},
    'common_harness_context':{
        'source':'source_parallel_13 reused by all groups; actual first-request comparisons in results/model_condition_validation.json',
        'native_SDK_Skill_disabled':True,'main_baseline_prepared':True,
        'external_SDK_tools_described_as_writable_despite_local_CLI_readonly':True,
        'interpretation_limit':'Some Development refusal/permission/branch lessons may overlap with harness fixes already supplied to B0. Assess this as a possible ceiling/redundancy explanation, not verified causation.'}}
for row in rows:
    prefix='posthoc_selection_matched_' if 'matched_prompt' in row['run_name'] else 'posthoc_'+a.stage+'_'
    path=OUT/'audit'/(prefix+row['task']+'_'+row['group']+'.md')
    data['individual_observational_audits'][str(path)]=path.read_text()
    evaluation=Path(row['eval_path']);data['official_evaluations'][str(evaluation)]=json.loads(evaluation.read_text())
    patch=Path(row['trajectory_path']).parent/'patch.diff';text=patch.read_text()
    data['final_student_patches'][str(patch)]=text if len(text)<=35000 else text[:35000]+f'\n[TRUNCATED {len(text)-35000} characters; complete original retained]'
recovery=OUT/'config/evaluation_triage.json'
if recovery.exists():data['evaluation_recovery']=json.loads(recovery.read_text())
recovery_audit=OUT/'audit/evaluation_diagnostic_selection_K2.md'
if recovery_audit.exists():data['evaluation_recovery_audit']=recovery_audit.read_text()
prompt='''Read-only pooled observational analysis in English, at most1800 words. All attempts are over. No output goes back to students or knowledge generation. Use original public requirements to assess the existing individual audits, particularly Selection audits which did not initially include that full description. Cite actual paths/event IDs from the audits and distinguish local tests from independent official F2P/P2P. Compare B0/K0/K1/K2: full success, partial correctness, retained functionality, execution behavior, unnecessary work, tool/request/token/time costs. Actual CLI input includes cache as a subset; SDK dollars are estimates, not settled billing. Separate input entry, behavior consistent with a rule, and causal attribution. Base may perform the same behavior. Do not infer that a single stochastic failure was caused by a library; describe concrete supporting or contrary evidence. Assess whether K2 supplies a substantive transferable constraint absent in K1 or merely a different organization/wording; the delivered libraries have different lengths and content despite shared sources/budgets. No source ablation means no marginal ranking of individual trajectories' learning value. This is one attempt per cell, not statistical significance or long-term capability proof. Do not suggest student code fixes, edit a skill, or use hidden tests/GT not present. For Selection, apply the already-saved retention rule (drop only for leakage, absent injection, invalid format, or regression with clear causal evidence; otherwise retain inconclusive candidates unchanged) and justify the evidence. For Test, all libraries were frozen beforehand; do not propose retrospective selection or tuning. End with confirmed findings, unresolved hypotheses, and specific limitations.\nEVIDENCE:\n'''+json.dumps(data,ensure_ascii=False,separators=(',',':'))
slug=a.stage+'_matched' if all('matched_prompt' in r['run_name'] for r in rows) else a.stage
path=OUT/'config'/f'pooled_{slug}_prompt.txt'
if len(prompt)>700000:raise RuntimeError('Pooled evidence exceeds input cap; inspect projection rather than silently dropping cases')
path.write_text(prompt)
print(json.dumps({'prompt':str(path),'characters':len(prompt)}))
