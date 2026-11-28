# Acquisition review interfaces

Implementation: `analysis/review_capability_acquisition.py`. All model operations run through the existing Claude Agent SDK and Codex CLI Bridge using GPT-6.1-terra / low. This script does not provide scientific judgments itself. It prepares evidence, invokes existing sessions, and aggregates observed usage or SDK-annotated semantic method labels.

No formal model review has been launched during implementation. `check` passed with valid synthetic PNG attachments, six anonymous prepared fixtures, and a running-student rejection check. The 24 anonymous IDs were frozen before test outcomes.

Commands use the existing environment Python. Stages:

- `freeze`: freeze anonymous IDs from the preselected task/group list; preserve an existing order.
- `library-audit`: after all generation/validation sessions finish and libraries freeze, before any test student starts. One session, 900 seconds / 60 requests, read-only evidence; no repair or additional condition-specific verification.
- `visual`: after all student supervisors finish. Anonymous reference + candidate images only, 600 seconds / 36 requests per run. No GT, library, group, prior score or target defect is supplied.
- `technical`: after all student supervisors finish and deterministic evaluator evidence is available, 900 seconds / 60 requests per run. Actual execution and posthoc evaluator evidence are separate.
- `knowledge-comparison`: after technical/visual reviews finish. One session, 700 seconds / 40 requests.
- `summarize`: observed usage for all four phases, plus ten library-pair semantic overlaps if actual audit/comparison annotations are available.
- `check`: synthetic/offline input checks, zero model calls.

`--prepare-only` writes the indexed inputs/jobs without starting a model. `--workers 2` is the default; 1, 2 or 4 are supported, with ports `19365 + lane` and CPU sets 32–39, 40–47, 64–71, 72–79. `--base-port` is configurable. Single audit/comparison sessions always use one worker. `--run ID` can select review jobs after the whole student phase ends. No job is started if its fixed time budget cannot fit before the experiment deadline, and active supervisors are stopped at the deadline margin.

Outputs under `acquisition_reviews/`:

- `library-audit/AUDIT/workspace/library_audit.json`: `conditions[*].canonical_semantic_methods`, canonical vocabulary, leakage/verification/origin audit. Numeric defaults and synthetic examples are allowed; old fixed answers/assets are not.
- `visual/AVnnn/workspace/visual_evaluation.json`: image-only spatial/appearance observations, objects/regions, uncertainty, optional coarse overall estimate, `human_rating:null`.
- `technical/<run>/workspace/technical_annotation.json`: actual `run_id`, `scene_id`, adoption phases/provenance, execution/verification/retention, side effects, spatial/material analyses, exact `semantic_correspondence`.
- `knowledge-comparison/COMPARISON/workspace/knowledge_comparison.json`: substantive methods/origins, matched contrasts, actual adoption and complementary/redundant cases, limits.

The technical `semantic_correspondence` array uses `{gt_instance_ids:[integer], gt_semantic_label:string, student_object_names:[string], confidence:high|medium|low|unknown, basis:[evidence], ambiguity:[limits], orientation_identifiability:string}`. IDs must come from actual GT instance records; student names must exist in the actual scene. Empty roots can refer to their actual descendant meshes. Unknown/repeated/symmetric matches are not forced. These are model-proposed, not human-reviewed correspondences; a separate deterministic evaluator decides whether a projection comparison is eligible. No alignment-dependent 3D errors are fabricated.

Adoption distinguishes SKILL text present in the original prompt, a later file Read, import only, actual function invocation, explicitly cited manual implementation, and semantic similarity of unknown origin. Teacher instructions and evaluator checks are never counted as student adoption.

Canonical method entries use `{canonical_label, definition, status:implemented|validated|unknown, module_functions_and_lines, actual_validation_evidence, origin_evidence, uncertainty}`. One common semantic vocabulary is requested across all five libraries. `analysis/acquisition_review_library_overlap.json` computes ten pairwise Jaccard values from actual implemented/validated SDK labels, preserving unknown coverage and annotation source. No code-text similarity is substituted for method overlap.

`analysis/acquisition_review_usage.json` preserves phase/session requests, observed token fields, missing-usage request IDs, actual model/effort, errors and status. USD billing remains unknown; no Ofox API is used. Raw requests, responses, SDK trajectory and execution logs remain in each normal SDK run directory. Inputs and per-file provenance are under `acquisition_review_inputs/`; the visual namespace receives only its two anonymous images.

## SDK research reporter

Stage `report` invokes one `research_reporter` SDK session, 900 seconds / 60 requests, tools Read/Write only, same model/effort/backend. It runs only after every frozen student supervisor ends, knowledge comparison ends, and `analysis/projection_summary.json` has `complete:true`, the expected run count, and every run `completed:true`. The English instruction asks the SDK model to write a Chinese `REPORT_ZH.md`, explicitly answering the ten study questions with evidence and limits. All report inputs are mounted read-only.

Raw report session: `acquisition_reviews/report/REPORT/`. The controller copies its actual `workspace/REPORT_ZH.md` unchanged to the experiment `REPORT_ZH.md`, with `infrastructure/acquisition_review_report_provenance.json` recording that operation. Major scientific conclusions are model-authored through the SDK, not supplied by the external controller.

`analysis/acquisition_review_research_usage.json` has `{recorded_at_utc, scopes, sessions, actual_billing_usd:null, ofox_requests:0, limitations}`. Each scope contains sessions, model_requests, known_tokens, requests_without_usage. Each session preserves scope, source_directory, status/resources, model_requests, known_tokens, requests_without_usage IDs, actual_models, reasoning_efforts and errors. It includes standard learning, validation, test students, all review phases and real SDK preflight directories. Reporter usage becomes available after its own completion; this file is refreshed then. Cached/reasoning token fields remain subsets.

`report --prepare-only` checks the same completion gates and creates selected evidence bundles/index without starting a model. The evidence includes protocol/configs/source origins/repair log, actual review JSONs, deterministic summaries and per-run results, real reference/final images, observed usage, and read-only links to the full technical evidence. Initial context is an index rather than concatenated raw trajectories. `knowledge-comparison` must precede it; projection comparison must follow technical annotations and precede it.

The original implementation snapshot remains in `acquisition_review_source/`; the completed reporter version is saved separately in `acquisition_review_source_with_report/`. No earlier experiment/source snapshot was overwritten.

## Bounded projection review after actual aggregate timeout

The real aggregate session exhausted its 700-second limit while combining all original mapping decisions with research comparison. Its ended run is preserved as `COMPARISON_pre_mapping_split`, following the earlier `COMPARISON_pre_input_limit` failure.

`projection-review --workers 4 --base-port 19565` starts four existing-SDK sessions, one per test scene and its six runs, 600 seconds / 36 requests each. Each namespace mounts only that scene's actual annotations/proposals/technical evidence. The source proposals have both exact JSONL indexing and a readable pretty-JSON copy; no GT ID/name/confidence/order is changed. The model writes `acquisition_reviews/projection-review/<scene>/workspace/projection_identity_review.json` incrementally.

After the batch, actual per-scene outputs are mechanically merged to `analysis/projection_identity_review.json`. `merge-projection-review` can explicitly repeat that deterministic merge. It reports expected/reviewed run and mapping counts, missing/duplicate/unexpected indices and `complete`. Missing model decisions are not invented. Root `projection_correspondence_review` preserves actual SDK decisions for the projector's existing `--comparison` interface.

`knowledge-comparison` no longer performs per-mapping eligibility or returns that schema. It retains 700 seconds / 40 requests and the actual 60,000-token SDK auto-compaction configuration. Start from `compact_comparison_evidence.json` (24 mechanically selected original annotation records and citations), observed tables and the pre-test audit, then inspect targeted source evidence. No controller scientific judgments are inserted. Readable indentation is an input-navigation improvement; the actual Read tool was not shown to have a character-per-line truncation limit.

The report reads `analysis/paired_projection_differences.json` and only treats two-sided measured same-scene exact-GT-ID-set pairs as matched projection contrasts. All prior student results, source snapshots, libraries, GT and Experiment 03-B remain unchanged. Model session costs, including the archived aggregates and new review stage, stay in the normal observed-usage accounting.

## Single missing-index followup after actual partial scene reviews

The original per-scene SDK reviewers ended voluntarily with partial JSONs. SDK `completed` is not mapping coverage. Original files remain unchanged. `projection-followup --workers 4 --base-port 19565` first requires all four original supervisor statuses to have finished and stopped their owned processes. It freezes exactly one plan at `configs/acquisition_review_projection_followup_plan.json`: one small job per run with originally absent mapping indices, 240 seconds / 16 requests. It never selects by eligibility values, revisits an existing index, or generates an automatic second round. Re-preparation reuses the frozen plan.

Each followup namespace contains only that run's exact original missing proposals and actual technical evidence. Original mapping indices are not renumbered. Outputs use the existing `projection_identity_review.json` schema under `acquisition_reviews/projection-followup/<run>/workspace/`. No model is needed for an actual empty original proposal array.

The mechanical merger combines fragments into one record per run and adds each decision's actual `decision_source` and `decision_stage`. Full original fragments remain available. Duplicate indices are retained and make coverage incomplete, rather than choosing a preferred answer. Missing decisions remain explicit `remaining_unreviewed` unknowns; they are not synthesized as model eligibility. The new stage is included in normal OUTPUTS/usage accounting.

The real aggregate comparison returned `libraries[*].methods` string lists and its own `semantic_jaccard`, without per-method validation statuses. Semantic-overlap summarization now computes exact-label set Jaccard for that actual schema and explicitly calls these declared methods, with validation status unavailable. The original structured canonical schema still uses its explicit implemented/validated status filter. All ten arithmetic values match the model's returned rounded values; no controller semantic relabeling was introduced and the raw comparison is unchanged.
