# Scene RSI Experiment 03-B — Perceptual Teacher Alignment Baselines

Independent of capability-learning Experiment03-A. Reuses the original Claude Agent SDK and Codex CLI Bridge with gpt-6.1-terra, low. Actual baseline versions are T0 (generic) and T1 (one human's provisional attention principle). T2 and T3 remain pending genuine human development feedback.

- `PROTOCOL.md`, `configs/`: frozen scene-level splits, equal critic budgets, source mappings and English prompts.
- `inputs/`: exactly two anonymous images per perceptual case.
- `reviews/`: fresh SDK critic sessions, actual model requests/responses, image associations, tools and usage.
- `predictions/`: preserved initial T0/T1 outputs, frozen before human feedback.
- `base_students/`: fresh no-Hint/no-capability reconstructions for two new independent references, two repetitions each.
- `human_review/development/index.html`: anonymous old-scene development form.
- `human_review/independent/index.html`: separate unseen-scene form, not for teacher adjustment.
- `analysis/`: mechanical prediction comparison, request audits and model-assisted research interpretation.
- `human_annotations/`: real exports only; none fabricated.
- `ENGINEERING_LOG.md`: actual integration and version changes.
- `REPORT_ZH.md`: Chinese research report after execution.

The form accepts a coarse0–100 fidelity rating, up to three important visible defects, optional severity/text and same-reference pair preferences. Every field starts empty. Browser-local autosave and separate JSON export work offline; copy the complete form directory with its PNG files if opening on another computer.

Import a genuine returned export using the existing environment Python and `analysis/human_teacher_alignment.py import --input /absolute/path/to/export.json`. The script preserves the original export in its declared split and produces auxiliary rank/preference/category comparisons. No human score is created by a model. To prepare T2/T3 evidence after development labels exist, run `analysis/human_teacher_alignment.py prepare-followup`; only development images, human exports and frozen T0/T1 predictions are copied. This command does not execute T2/T3. Independent human labels and independent teacher outputs remain excluded from adjustment.

Future stages reuse `harness/run_sdk_session.py`; no new Agent loop is introduced. Perceptual Critic uses RGB only. Technical Diagnostician may separately inspect code/state/trajectory, optionally authorized developmentGT. Exploration Teacher may later design competing hints and verification from that diagnosis. Technical causes, unseen3D errors and exploration outcomes are not inferred from an RGB-only critique.

Before T2/T3 execution, select a separate selection-scene set, match inference budgets, validate candidates, freeze teacher versions and retain the independent scene-level holdout. Single-rater feedback measures that person's judgment agreement; it cannot establish general human alignment. Rankings, category overlap and automated scores are auxiliary measures, not a validated composite quality score.

Completed batch:32 formal perceptual critic sessions (12 development cases plus4 independent cases, T0/T1 each),4 new Base student sessions,4 source-only pixel-identical regenerations and1 SDK research reporter. Five completed plus one interrupted pre-isolation-fix sessions are preserved separately, giving43 total session records. No human annotations, T2 or T3 were fabricated. The model-authored Chinese report is `REPORT_ZH.md`; its unedited source remains under `research_analyses/research_reporter/workspace/`. The controller only clarified parameter scopes/links and appended final numeric accounting. See `completion.json`, `analysis/report_fact_checks.json` and `analysis/usage_summary.json`.
