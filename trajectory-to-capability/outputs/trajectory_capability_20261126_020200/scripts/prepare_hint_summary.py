"""Prepare final user-facing Hint evidence, after optional execution closes."""
import json
from pathlib import Path

OUT=Path.cwd()/'outputs/trajectory_capability_20261126_020200'
state=json.loads((OUT/'runs/hint_exploration_state.json').read_text())
if state['status']=='running':raise RuntimeError('Optional student execution is still running')
rows=json.loads((OUT/'results/hint_attempt_metrics.json').read_text())
data=dict(plan=json.loads((OUT/'config/optional_hint_plan.json').read_text()),
    metrics=rows,condition_validation=json.loads((OUT/'results/hint_condition_validation.json').read_text()),
    posthoc_audits={},official_evaluations={})
for row in rows:
    if row['trajectory_path']:
        audit=OUT/'audit'/('posthoc_hint_exploration_'+row['task']+'_'+row['group']+'.md')
        if not audit.exists():raise RuntimeError('Finish individual post-hoc audit before summary: '+str(audit))
        data['posthoc_audits'][str(audit)]=audit.read_text()
    if row['eval_path']:data['official_evaluations'][row['eval_path']]=json.loads(Path(row['eval_path']).read_text())
progress=OUT/'logs/hint_progress/progress.jsonl'
data['teacher_checks']=[json.loads(line) for line in progress.open()] if progress.exists() else []
timeout_record=OUT/'logs/optional_evaluation_timeout_NoHint.json'
if timeout_record.exists():data['first_manual_timeout_record']=json.loads(timeout_record.read_text())
repair=OUT/'audit/optional_evaluation_repair_zh.md'
if repair.exists():data['optional_evaluation_repair_scope']=repair.read_text()
prompt='''Write a final Chinese user-facing observational Hint-exploration addendum, about1500-2300 Chinese characters, using only this completed evidence. This will be inserted after the actual result table in the final report. Cite source paths/event numbers and link only actual files using absolute /srv/... paths, never file://. Compare actual Error/Strategy/Exploration Hint content, whether each is faithful to the requested style, and NoHint. Explicitly distinguish SDK callbacks, one permitted actual teacher check, candidate and screening calls, delivered Hint words, actual next-request entry, and behavior afterward. State which treatment was actually delivered; a named arm with no delivered Hint is not evidence for that style. Different observed trajectories start from the same initial code with new independent sessions, not a common intermediate state; check actual initial-request equality proof. Report immediate formal success/F2P/P2P and student/teacher costs from exact metrics without inventing missing data. The table already reports all planned arms; do not duplicate it. Distinguish real partial/algorithmic failures, technical/evaluation interruptions and deadline skips. Match a Hint with concrete subsequent actions, but do not turn temporal order or a model self-claim into causality. NoHint may do similar probes on its own. Candidate transferable observations may be noted as unverified; no new skill, independent Hint-to-knowledge transfer test, or main-library update was performed. All primary four-group Test libraries were frozen before these optional trials. Do not claim a ranking of long-term trajectory learning value from final task grades. If the evidence does not support a style effect, say so. Keep the scope narrow and factual; do not propose student task code fixes.\nEVIDENCE:\n'''+json.dumps(data,ensure_ascii=False,separators=(',',':'))
(OUT/'config/hint_exploration_summary_prompt.txt').write_text(prompt)
print(json.dumps({'characters':len(prompt)}))
