# Projection eligibility preflight v2

The original 34-check preflight and all its images, logs and measurements remain unchanged under ../projection_metrics. Before this change, both source files and the original check/summary JSON were copied to ../projection_metrics/v1/.

A real posthoc input issue was identified before formal projection: original technical-review ambiguity arrays often contain shape, texture, visibility or general verification limits rather than uncertainty about entity identity. The controller does not interpret these strings. The already-planned SDK knowledge-comparison session now supplies a separate projection_correspondence_review; no additional model stage is introduced.

The v2 filter requires the unchanged original confidence to be high, the corresponding comparison mapping_index to explicitly set measurement_eligible:true, and identity_ambiguity to explicitly equal an empty array. Missing, false, null or identity-ambiguous eligibility remains unknown. Original GT IDs, exact student names, confidence, order and ambiguity remain unchanged. Non-identity limits, basis and reason are retained in the result. GT ID, duplicate assignment, exact rendering-name and rendering validation checks remain.

Six independent synthetic fixtures reuse unchanged v1 geometry. Actual aligned and shifted scenes with general caveats are measured after explicit eligibility, with mask pixels and IoU identical to their v1 results. Explicit identity uncertainty, original low confidence despite eligible:true, missing eligibility and null eligibility all remain unknown. Focused host checks additionally confirm true eligibility cannot clear nonempty identity ambiguity, no eligibility field cannot pass, invalid IDs/empty names/duplicates remain unknown, and the proposal is not modified. These synthetic review inputs are engineering test data, not actual SDK or human scientific annotations.

See actual_checks.json, source_origin.json, source/ and each actual per-run command, render, mask, overlay and output. No formal projection, student, frozen library or runtime was changed by this work.

Formal order: SDK technical annotations -> the existing planned SDK knowledge comparison -> deterministic projection -> final report. The CLI remains:

    /srv/lab-disks/disk2/users/xymo/miniforge3/envs/scenemosaic/bin/python analysis/measure_acquisition_projection.py --workers 4

Default comparison source: acquisition_reviews/knowledge-comparison/COMPARISON/workspace/knowledge_comparison.json. The final projection summary records the review source, availability and v2 protocol version. An absent comparison source keeps complete:false; unavailable per-mapping eligibility never creates a score.
